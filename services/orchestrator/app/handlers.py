"""Workflow handler registry.

WorkflowHandlers holds the async specialist callables the executable graph nodes call.
Each takes and returns EnquiryState. Blocking states (await_ocr, confirm, clarify,
review) are graph interrupts, NOT handlers: the ``review`` interrupt is resolved out-of-band
by the route-invoked approval/rejection/revision services (prompt 14, app.approval and
app.revisions), which hold the enquiry lock and own publication. Production startup fails
readiness until every required handler is registered — we never ship runnable fake-success
nodes (prompt 09). Test doubles are injected only by tests.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, fields
from typing import Any, Protocol
from uuid import UUID

from app.features.f17_multi_part_enquiries import unresolved_ids
from app.features.f44_conversation_summary import is_stale as _summary_is_stale
from app.features.f48_input_isolation import F48Request, validate_tool_call
from app.rendering import render_reply
from app.specialists.reply import draft_reply
from app.verification import VerificationStore, run_verification
from partsiq_common.contracts import (
    BudgetReservation,
    EnquiryState,
    Locale,
    ReplySlots,
    VerifiedFacts,
)
from partsiq_common.errors import PartsIQError

Handler = Callable[[EnquiryState], Awaitable[EnquiryState]]


def unresolved_items(state: EnquiryState) -> list[UUID]:
    """F17: item ids that are not yet ``ready`` for the current workflow state.

    The graph's plan/review path and the /internal/items/resolve route share this single
    readiness rule (app.features.f17_multi_part_enquiries.unresolved_ids), so the executable
    workflow and the API agree on exactly when an all-items recommendation may be approved —
    one unresolved item blocks the final all-items approval.
    """
    return unresolved_ids(state.items)


def reset_derived_state(state: EnquiryState) -> EnquiryState:
    """F38: after a correction, clear everything DERIVED from the old facts and re-enter the graph.

    A correction invalidates the draft, the verification and any pending question (and, upstream,
    the candidate selections), so recomputation starts again from intake. Publication/approval is
    never carried across a correction. This is the single reset the correction-recomputation event
    applies when it re-enters the workflow.
    """
    return state.model_copy(
        update={"draft_id": None, "verification_id": None, "pending_question": None, "phase": "intake"}
    )


def summary_needs_refresh(state: EnquiryState, summary_revision: int) -> bool:
    """F44: a stored conversation summary must be regenerated once the revision has moved on."""
    return _summary_is_stale(summary_revision, state.revision)


def guard_tool_call(tool_name: str, arguments_json: str, context) -> None:
    """F48: refuse any model-proposed tool call that is not an allowlisted, typed read tool.

    Every tool the parts specialist dispatches passes through here first, so a prompt-injected
    instruction cannot invoke a write tool, change roles, reveal secrets, or add an argument.
    Raises VALIDATION_FAILED carrying the isolation reason code; the string arguments stay inert
    data once allowed.
    """
    verdict = validate_tool_call(F48Request(tool_name=tool_name, arguments_json=arguments_json, context=context))
    if not verdict.allowed:
        raise PartsIQError("VALIDATION_FAILED", internal_detail=f"tool call blocked: {verdict.reason_code}")


@dataclass(frozen=True, slots=True)
class WorkflowHandlers:
    intake: Handler
    identify: Handler
    search: Handler
    choose: Handler
    plan: Handler
    draft: Handler
    verify: Handler


REQUIRED_HANDLERS = tuple(f.name for f in fields(WorkflowHandlers))


def missing_handlers(handlers: WorkflowHandlers | None) -> list[str]:
    """Return the names of handlers not yet registered (readiness gate)."""
    if handlers is None:
        return list(REQUIRED_HANDLERS)
    return [name for name in REQUIRED_HANDLERS if getattr(handlers, name, None) is None]


def is_ready(handlers: WorkflowHandlers | None) -> bool:
    return not missing_handlers(handlers)


def make_verify_handler(store: VerificationStore) -> Handler:
    """Adapt the deterministic verification gate (prompt 12) into the graph's ``verify`` node.

    The owner wires this handler so the executable node loads the current facts+evidence,
    runs the named rule set, persists exactly one result for the current (enquiry, revision)
    and records the verification id on the state — which routes the workflow to human review.
    Pass/fail is decided in code, never by an LLM (CONSTRAINTS rule 5); a failed result is
    carried forward for the reviewer to see, never silently treated as success. The store is
    injected so the gate is testable offline and the live adapter is supplied at startup.
    """

    async def verify(state: EnquiryState) -> EnquiryState:
        _result, verification_id = await run_verification(
            state.enquiry_id, state.revision, store=store
        )
        return state.model_copy(update={"verification_id": verification_id, "phase": "verified"})

    return verify


class DraftStore(Protocol):
    """Loads the current verified facts+locale and persists one draft per (enquiry, revision)."""

    async def load_facts(self, enquiry_id: UUID, revision: int) -> tuple[VerifiedFacts, Locale] | None: ...

    async def persist_draft(
        self,
        enquiry_id: UUID,
        revision: int,
        locale: Locale,
        slots: ReplySlots,
        facts: VerifiedFacts,
        rendered_text: str,
    ) -> UUID: ...


def make_draft_handler(store: DraftStore, *, budget: BudgetReservation, client: Any | None = None) -> Handler:
    """Adapt the reply specialist + renderer (prompt 13) into the graph's ``draft`` node.

    The model fills only the prose slots; the renderer inserts every fact in a code-owned
    layout. A provider/credit failure is surfaced (phase ``needs_staff_draft``) so staff can
    author a controlled draft through the same slot schema (F45) rather than the workflow
    emitting an un-reviewed or faked reply. The store is injected for offline testing.
    """

    async def draft(state: EnquiryState) -> EnquiryState:
        loaded = await store.load_facts(state.enquiry_id, state.revision)
        if loaded is None:
            raise PartsIQError("NOT_FOUND", internal_detail="no verified facts to draft from")
        facts, locale = loaded
        try:
            slots = await draft_reply(facts, locale, budget=budget, client=client)
        except PartsIQError as exc:
            if exc.code in ("DEPENDENCY_UNAVAILABLE", "CREDIT_UNAVAILABLE"):
                # No paid fallback (ADR-015): hand off to staff authoring, do not fabricate prose.
                return state.model_copy(update={"phase": "needs_staff_draft"})
            raise
        rendered = render_reply(slots, facts, locale)
        draft_id = await store.persist_draft(state.enquiry_id, state.revision, locale, slots, facts, rendered)
        return state.model_copy(update={"draft_id": draft_id, "phase": "drafted"})

    return draft
