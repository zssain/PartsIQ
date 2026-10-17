"""The plain durable workflow runner — an ordinary Python loop, NO LangGraph.

``run_next(state, handlers, repo)`` drives the journey by:

1. computing :func:`partsiq.workflow.transitions.next_step` from the typed state (pure Python,
   no LLM ever picks the step);
2. if the step waits (await_ocr/confirm/clarify/review) or is terminal (complete/needs_staff),
   SUSPENDING — it returns the state and the reason without busy-waiting; a slow external step
   resumes later from a committed job + wait state;
3. otherwise dispatching to the matching INJECTED handler, hashing the canonical step input,
   persisting exactly one :class:`StepOutcome`, and advancing the state.

It is DURABLE: a step whose result is already committed for this (enquiry, revision) is replayed
as a no-op (the handler is not re-invoked). It is FENCED: a commit is rejected — the result
discarded — if the enquiry revision or the demo session generation changed since the step began
(F50). Handlers are injected (filled by prompts 10-13 via the :class:`StepHandlers` registry);
this module imports no unfinished feature module. ``langgraph`` is NOT imported.

Replaces the discarded LangGraph ``graph.py``/``runner.py``/event-consumer wrapper from the
earlier build with a single explicit loop.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, fields
from enum import StrEnum
from uuid import UUID

from partsiq.core.contracts import EnquiryState, WorkflowStep
from partsiq.core.errors import PartsIQError

from .repository import WorkflowFence, WorkflowRepository
from .state import advance
from .transitions import is_executable, is_terminal, is_waiting, next_step

# A handler takes the current typed state and returns the state fields it updated, plus a
# machine-readable reason code for the StepOutcome. It performs the external/domain work for
# exactly one step; it does NOT decide the next step and does NOT persist.
HandlerResult = tuple[dict[str, object], str | None]
Handler = Callable[[EnquiryState], Awaitable[HandlerResult]]


@dataclass(frozen=True, slots=True)
class StepHandlers:
    """Registry of injected per-step handlers (filled by prompts 10-13).

    Exactly the executable steps have handlers. Blocking states (await_ocr, confirm, clarify,
    review) and terminal states (complete, needs_staff) are NOT handlers: the runner suspends
    or stops at those and they are resolved out-of-band (OCR job, customer answer, reviewer
    approval). Readiness fails until every required handler is registered — a fake-success
    node is never shipped in application code.
    """

    intake: Handler | None = None
    identify: Handler | None = None
    search: Handler | None = None
    choose: Handler | None = None
    plan: Handler | None = None
    draft: Handler | None = None
    verify: Handler | None = None

    def for_step(self, step: WorkflowStep) -> Handler | None:
        return getattr(self, step.value, None)


REQUIRED_HANDLERS: tuple[str, ...] = tuple(f.name for f in fields(StepHandlers))


def missing_handlers(handlers: StepHandlers | None) -> list[str]:
    """Return the names of handlers not yet registered (readiness gate)."""
    if handlers is None:
        return list(REQUIRED_HANDLERS)
    return [name for name in REQUIRED_HANDLERS if getattr(handlers, name, None) is None]


def is_ready(handlers: StepHandlers | None) -> bool:
    return not missing_handlers(handlers)


class RunStatus(StrEnum):
    """Outcome of one :func:`run_next` invocation."""

    ADVANCED = "advanced"  # a step ran and the state moved forward
    REPLAYED = "replayed"  # the step was already committed; resumed without re-running
    WAITING = "waiting"  # suspended awaiting an external/human event
    TERMINAL = "terminal"  # the run ended (complete or needs_staff)
    FENCED = "fenced"  # the result was discarded because the fence no longer holds


@dataclass(frozen=True, slots=True)
class RunResult:
    status: RunStatus
    step: WorkflowStep
    state: EnquiryState
    reason: str | None = None


def canonical_input_hash(state: EnquiryState, step: WorkflowStep) -> str:
    """SHA256 over the canonical inputs to ``step`` for this (enquiry, revision).

    The hash lets the repository reuse a completed step only when its exact inputs AND revision
    match; a different revision or payload produces a different hash and is not reused.
    """
    payload = {
        "enquiry_id": str(state.enquiry_id),
        "revision": state.revision,
        "step": step.value,
        "state": state.model_dump(mode="json"),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def run_next(
    state: EnquiryState,
    handlers: StepHandlers,
    repo: WorkflowRepository,
    *,
    lease_token: UUID,
) -> RunResult:
    """Execute (at most) one workflow step and return the resulting state.

    The next step is chosen purely by :func:`next_step` — no model is consulted. External work
    happens in the injected handler BEFORE the fenced commit, so no provider call holds a lock
    and a stale worker's output is discarded rather than committed (F50).
    """
    step = next_step(state)

    # Suspend at an external/human wait; the run resumes later from committed state + a wait
    # record (no busy-waiting).
    if is_waiting(step):
        return RunResult(status=RunStatus.WAITING, step=step, state=state, reason=step.value)

    # Stop at a terminal state.
    if is_terminal(step):
        return RunResult(status=RunStatus.TERMINAL, step=step, state=state, reason=step.value)

    if not is_executable(step):  # pragma: no cover - defensive; table only yields the above
        raise PartsIQError(
            "CONFLICT", internal_detail=f"no dispatch rule for workflow step {step.value}"
        )

    input_hash = canonical_input_hash(state, step)

    # DURABLE replay: if this exact step+inputs is already committed, resume from the committed
    # result without re-invoking the handler (idempotent — publication/work never repeats).
    recorded = await repo.load_recorded(state.enquiry_id, state.revision, step)
    if recorded is not None and recorded.input_hash == input_hash:
        updates = _updates_from_outcome(recorded.outcome.data)
        advanced = advance(state.model_copy(update=updates))
        return RunResult(status=RunStatus.REPLAYED, step=step, state=advanced, reason=recorded.outcome.reason_code)

    handler = handlers.for_step(step)
    if handler is None:
        raise PartsIQError(
            "DEPENDENCY_UNAVAILABLE",
            internal_detail=f"workflow handler for {step.value} is not registered",
        )

    # External/domain work happens here, outside any lock.
    updates, reason_code = await handler(state)

    # One StepOutcome per step. The envelope is a concrete typed dict of the state updates;
    # it is not permission to store arbitrary provider output.
    from partsiq.core.api_models import StepOutcome  # local import keeps module import-light

    outcome = StepOutcome(step=step, reason_code=reason_code, data=dict(updates))

    fence = WorkflowFence(
        enquiry_id=state.enquiry_id,
        revision=state.revision,
        session_generation=state.session_generation,
        lease_token=lease_token,
    )
    committed = await repo.commit_step(fence, step, input_hash, outcome)
    if not committed:
        # The revision/generation moved or the lease expired: discard the output, do not
        # advance. The enquiry's current run (new revision/generation) proceeds independently.
        return RunResult(status=RunStatus.FENCED, step=step, state=state, reason="stale_fence")

    advanced = advance(state.model_copy(update=dict(updates)))
    return RunResult(status=RunStatus.ADVANCED, step=step, state=advanced, reason=reason_code)


def _updates_from_outcome(data: dict[str, object]) -> dict[str, object]:
    """Only the EnquiryState fields present in a stored outcome envelope are re-applied."""
    allowed = set(EnquiryState.model_fields)
    return {k: v for k, v in data.items() if k in allowed}
