"""Workflow handler registry.

WorkflowHandlers holds the async specialist callables the executable graph nodes call.
Each takes and returns EnquiryState. Blocking states (await_ocr, confirm, clarify,
review) are graph interrupts, NOT handlers. Production startup fails readiness until
every required handler is registered — we never ship runnable fake-success nodes
(prompt 09). Test doubles are injected only by tests.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, fields

from app.verification import VerificationStore, run_verification
from partsiq_common.contracts import EnquiryState

Handler = Callable[[EnquiryState], Awaitable[EnquiryState]]


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
