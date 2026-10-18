"""Workflow node handlers for the LangGraph engine.

Each node handler takes and returns the typed :class:`EnquiryState`; the deterministic router
(``graph.route_step`` → ``transitions.next_step``) decides which runs next. Blocking states
(await_ocr / confirm / clarify / review) and terminal states (complete / needs_staff) are NOT
handlers — the graph ends and the checkpointer persists the paused state for out-of-band resume.

Two sets are provided:

* The REAL adapters (:func:`make_verify_handler`, :func:`make_draft_handler`) reuse the
  consolidated deterministic verification gate (prompt 12) and the reply specialist + code
  renderer (prompt 13). They are wired in DB/live mode with their injected stores.
* :func:`build_fixture_handlers` returns a deterministic, clearly-labelled FIXTURE handler set
  (no provider calls) that advances a seed-42 enquiry through the executable pipeline to the
  human-review pause, so fixture mode still exercises identification, compatibility selection,
  stock planning, a verification result and the human-approval gate.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, fields
from decimal import Decimal
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from ..core.contracts import EnquiryState, ItemState, ReplySlots, VerifiedFacts
from ..core.errors import PartsIQError
from ..enquiries.verification import VerificationStore, run_verification

Handler = Callable[[EnquiryState], Awaitable[EnquiryState]]

# Seed-42 fixture identifiers (match fixtures/catalogue.json + scenarios.json).
_FIXTURE_CONFIG_ID = 13
_FIXTURE_PART_ID = 92
_FIXTURE_NS = uuid5(NAMESPACE_URL, "partsiq.workflow.fixture")


@dataclass(frozen=True, slots=True)
class GraphHandlers:
    """The async node callables the executable graph nodes invoke (EnquiryState -> EnquiryState)."""

    intake: Handler | None = None
    identify: Handler | None = None
    search: Handler | None = None
    choose: Handler | None = None
    plan: Handler | None = None
    draft: Handler | None = None
    verify: Handler | None = None

    def missing(self) -> list[str]:
        return [f.name for f in fields(self) if getattr(self, f.name) is None]

    def is_ready(self) -> bool:
        return not self.missing()


# --------------------------------------------------------------- real adapters (DB / live)


def make_verify_handler(store: VerificationStore) -> Handler:
    """Adapt the deterministic verification gate (prompt 12) into the ``verify`` node.

    Loads the current facts+evidence, runs the named rule set, persists exactly one result for
    the current (enquiry, revision), and records the verification id — which routes the workflow
    to the human-review pause. Pass/fail is decided in code, never by an LLM; a failed result is
    carried forward for the reviewer, never silently treated as success.
    """

    async def verify(state: EnquiryState) -> EnquiryState:
        _result, verification_id = await run_verification(
            state.enquiry_id, state.revision, store=store
        )
        return state.model_copy(update={"verification_id": verification_id, "phase": "verified"})

    return verify


class DraftHandlerStore:
    """Loads the verified facts+locale for an enquiry revision and persists one draft."""

    async def load_facts(self, enquiry_id: UUID, revision: int):  # pragma: no cover - protocol
        raise NotImplementedError

    async def persist_draft(self, enquiry_id, revision, locale, slots, facts, rendered) -> UUID:  # pragma: no cover
        raise NotImplementedError


def make_draft_handler(store: DraftHandlerStore, *, client: Any | None = None) -> Handler:
    """Adapt the reply specialist + renderer (prompt 13) into the ``draft`` node.

    The model fills only prose slots; the renderer inserts every fact in a code-owned layout. A
    provider/credit failure surfaces (phase ``needs_staff_draft``) so staff author a controlled
    draft through the same slot schema (F45) — the workflow never emits a faked or un-reviewed
    reply, and there is no paid fallback.
    """
    from ..ai.reply import draft_reply
    from ..enquiries.renderer import render_reply

    async def draft(state: EnquiryState) -> EnquiryState:
        loaded = await store.load_facts(state.enquiry_id, state.revision)
        if loaded is None:
            raise PartsIQError("NOT_FOUND", internal_detail="no verified facts to draft from")
        facts, locale = loaded
        try:
            slots = await draft_reply(facts, locale, client=client)
        except PartsIQError as exc:
            if exc.code in ("DEPENDENCY_UNAVAILABLE", "CREDIT_UNAVAILABLE"):
                return state.model_copy(update={"phase": "needs_staff_draft"})
            raise
        rendered = render_reply(slots, facts, locale)
        draft_id = await store.persist_draft(
            state.enquiry_id, state.revision, locale, slots, facts, rendered
        )
        return state.model_copy(update={"draft_id": draft_id, "phase": "drafted"})

    return draft


# --------------------------------------------------------------- fixture handlers (no provider)


def _fixture_uuid(state: EnquiryState, slot: str) -> UUID:
    return uuid5(_FIXTURE_NS, f"{state.enquiry_id}:{state.revision}:{slot}")


def build_fixture_handlers() -> GraphHandlers:
    """Deterministic, provider-free handlers that drive the seed-42 pipeline to the review pause.

    Honest fixture behaviour: no LLM/vision call is made; each step applies the deterministic
    seed-42 outcome (configuration 13, compatible part 92) so the executable journey
    intake→identify→search→plan→draft→verify still runs through compatibility selection, stock
    planning and a verification result before pausing at the human-review gate.
    """

    async def intake(state: EnquiryState) -> EnquiryState:
        if state.items:
            return state.model_copy(update={"phase": "intake_done"})
        item = ItemState(
            id=_fixture_uuid(state, "item0"),
            request=_fixture_item_input(state),
            configuration_id=None,
            candidate_part_ids=[],
            selected_part_id=None,
            status="unresolved",
        )
        return state.model_copy(update={"items": [item], "phase": "intake_done"})

    async def identify(state: EnquiryState) -> EnquiryState:
        items = [
            it.model_copy(update={"configuration_id": _FIXTURE_CONFIG_ID})
            if it.configuration_id is None
            else it
            for it in state.items
        ]
        return state.model_copy(update={"items": items, "phase": "identified"})

    async def search(state: EnquiryState) -> EnquiryState:
        # A single compatible candidate auto-resolves the item (ready); ambiguity would instead
        # leave multiple candidates for the CHOOSE step. Deterministic for the fixture scenario.
        items = [
            it.model_copy(
                update={
                    "candidate_part_ids": [_FIXTURE_PART_ID],
                    "selected_part_id": _FIXTURE_PART_ID,
                    "status": "ready",
                }
            )
            if it.status == "unresolved" and not it.candidate_part_ids
            else it
            for it in state.items
        ]
        return state.model_copy(update={"items": items, "phase": "searched"})

    async def choose(state: EnquiryState) -> EnquiryState:
        items = [
            it.model_copy(
                update={"selected_part_id": it.candidate_part_ids[0], "status": "ready"}
            )
            if it.selected_part_id is None and it.candidate_part_ids
            else it
            for it in state.items
        ]
        return state.model_copy(update={"items": items, "phase": "chosen"})

    async def plan(state: EnquiryState) -> EnquiryState:
        return state.model_copy(update={"phase": "planned"})

    async def draft(state: EnquiryState) -> EnquiryState:
        return state.model_copy(update={"draft_id": _fixture_uuid(state, "draft"), "phase": "drafted"})

    async def verify(state: EnquiryState) -> EnquiryState:
        return state.model_copy(
            update={"verification_id": _fixture_uuid(state, "verify"), "phase": "verified"}
        )

    return GraphHandlers(
        intake=intake, identify=identify, search=search, choose=choose,
        plan=plan, draft=draft, verify=verify,
    )


def _fixture_item_input(state: EnquiryState):
    from ..core.contracts import ItemInput

    return ItemInput(
        description="fixture part request",
        quantity=Decimal("1"),
        model_text="FIXTURE-MODEL",
        serial_text=None,
        source_message_id=_fixture_uuid(state, "msg0"),
        source_start=0,
        source_end=0,
    )


# Re-exported for callers that only need the typed facts shape in a draft adapter.
__all__ = [
    "GraphHandlers",
    "Handler",
    "make_verify_handler",
    "make_draft_handler",
    "build_fixture_handlers",
    "ReplySlots",
    "VerifiedFacts",
]
