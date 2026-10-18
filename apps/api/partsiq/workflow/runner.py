"""The durable workflow runner.

The AUTHORITATIVE engine is LangGraph (``graph.build_graph`` + the Postgres/InMemory
checkpointer); :func:`run_workflow` drives a compiled graph to the next durable pause and records
one :class:`StepOutcome` per executed node to the :class:`WorkflowRepository` so the staff
specialist timeline can show each step's inputs/outputs/failures. Routing is always the
deterministic :func:`partsiq.workflow.transitions.next_step` — no LLM ever picks the step.

:func:`run_next` is the lower-level deterministic STEP PRIMITIVE retained alongside the graph: it
computes the next step, dispatches to an injected handler, hashes the canonical input, persists
exactly one :class:`StepOutcome`, and advances the state — with the same DURABLE replay (a step
already committed for this (enquiry, revision) is a no-op) and FENCED commit (discarded if the
revision or demo generation moved, or the lease expired, F50). The graph owns resume/checkpoint
state; this primitive owns the fenced, de-duplicated step-outcome log that the timeline and the
no-replay guarantee read from. Both share the one transition table, so they can never disagree
about which step is next.
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


async def run_workflow(
    graph,
    state: EnquiryState,
    *,
    thread_id: str,
    repo: WorkflowRepository | None = None,
    fence: "WorkflowFence | None" = None,
) -> RunResult:
    """Drive a compiled LangGraph to the next durable pause/terminal and return the result.

    LangGraph executes the deterministic nodes and persists the paused state at its checkpoint
    (keyed by ``thread_id`` = ``enquiry:{id}:rev:{revision}``) so a blocking step (await_ocr /
    confirm / clarify / review) or a terminal step resumes out-of-band. When ``repo`` is given,
    each executed node is recorded as one :class:`StepOutcome` for the staff timeline; recording
    is fenced by ``fence`` (a result for a superseded revision/generation is not recorded).

    Routing is :func:`next_step`; no model picks the step. Returns the final state plus a status
    describing whether the run advanced, is WAITING on an external/human event, or is TERMINAL.
    """
    from ..core.api_models import StepOutcome

    config = {"configurable": {"thread_id": thread_id}}
    final = state
    # stream_mode="updates" yields {node_name: state_delta} after each node, giving us the exact
    # ordered node sequence for the timeline; the checkpointer records the paused state for resume.
    async for update in graph.astream(state, config, stream_mode="updates"):
        for node_name, delta in update.items():
            if isinstance(delta, EnquiryState):
                final = delta
            elif isinstance(delta, dict):
                final = final.model_copy(update=delta)
            # Record one fenced StepOutcome per executed node for the staff timeline. Recording
            # needs the fence context (revision/generation/lease) so a superseded run's nodes are
            # not written; without a fence we skip recording and let the graph run.
            if repo is not None and fence is not None:
                try:
                    step = WorkflowStep(node_name)
                except ValueError:
                    continue
                outcome = StepOutcome(
                    step=step,
                    reason_code=final.phase or None,
                    data={"phase": final.phase, "step_count": final.step_count},
                )
                await repo.commit_step(fence, step, canonical_input_hash(final, step), outcome)

    step = next_step(final)
    if is_waiting(step):
        return RunResult(status=RunStatus.WAITING, step=step, state=final, reason=step.value)
    if is_terminal(step):
        return RunResult(status=RunStatus.TERMINAL, step=step, state=final, reason=step.value)
    return RunResult(status=RunStatus.ADVANCED, step=step, state=final, reason=final.phase or None)
