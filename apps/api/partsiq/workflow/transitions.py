"""The FIXED workflow transition table — ordinary Python, no LLM, no agent framework.

``next_step(state) -> WorkflowStep`` is a PURE function of the typed :class:`EnquiryState`.
It is evaluated top-to-bottom; the first matching rule wins. There is no I/O, no provider
call and no model inference here: an LLM NEVER decides which step runs next (ADR-003,
CONSTRAINTS rule 5, F50). The journey and every edge below are the table in
``docs/WORKFLOW.md`` expressed as code so each decision is testable on labelled cases and
cannot be overridden by model output.

Ported from the earlier build's ``services/orchestrator/app/controller.py`` (whose
``next_step`` was already plain Python). The LangGraph ``graph.py`` wrapper that previously
routed to this function is DISCARDED; the plain :mod:`partsiq.workflow.runner` loop replaces
it. ``langgraph`` is NOT imported anywhere in this package.
"""
from __future__ import annotations

from partsiq.core.contracts import EnquiryState, ItemState, WorkflowStep

# Bounded transition count before escalation (WORKFLOW_MAX_STEPS default in
# spec/environment.json). A run that exceeds this is an unexpected loop and is sent to
# staff rather than cycling forever (prompt 09 step 11).
MAX_STEPS = 12

# Steps the runner can dispatch to an injected handler. The remaining steps are either
# external waits (AWAIT_OCR), customer/staff interrupts (CONFIRM, CLARIFY, REVIEW) or
# terminal (COMPLETE, NEEDS_STAFF); the runner suspends/stops at those rather than calling
# an automatic handler.
EXECUTABLE_STEPS: frozenset[WorkflowStep] = frozenset(
    {
        WorkflowStep.INTAKE,
        WorkflowStep.IDENTIFY,
        WorkflowStep.SEARCH,
        WorkflowStep.CHOOSE,
        WorkflowStep.PLAN,
        WorkflowStep.DRAFT,
        WorkflowStep.VERIFY,
    }
)

# Steps where the run pauses durably waiting for something outside the automatic loop:
# an external job (OCR), the customer (confirmation, clarification answer) or a reviewer.
WAITING_STEPS: frozenset[WorkflowStep] = frozenset(
    {
        WorkflowStep.AWAIT_OCR,
        WorkflowStep.CONFIRM,
        WorkflowStep.CLARIFY,
        WorkflowStep.REVIEW,
    }
)

# Steps that end the run: either the recommendation is approved/published (COMPLETE) or the
# enquiry has been handed to a human (NEEDS_STAFF).
TERMINAL_STEPS: frozenset[WorkflowStep] = frozenset(
    {WorkflowStep.COMPLETE, WorkflowStep.NEEDS_STAFF}
)

# Phases meaning a human/approval decision has already been recorded; review is complete and
# the only remaining automatic edge is to COMPLETE.
_REVIEWED_PHASES: frozenset[str] = frozenset({"reviewed", "approved", "complete"})


# The allowed-transition set: every (current_step -> next_step) edge the table may ever
# produce. It is derived mechanically from ``next_step`` so tests can assert that a computed
# transition is a declared edge and that no undeclared edge is ever taken. ``current`` is the
# step the run is presently executing/resting at; ``next`` is what ``next_step`` yields once
# that step's outcome has been applied to the state.
ALLOWED_TRANSITIONS: frozenset[tuple[WorkflowStep, WorkflowStep]] = frozenset(
    {
        # intake: text parsed -> identify or clarify; validated image needs reading -> await_ocr.
        (WorkflowStep.INTAKE, WorkflowStep.IDENTIFY),
        (WorkflowStep.INTAKE, WorkflowStep.CLARIFY),
        (WorkflowStep.INTAKE, WorkflowStep.AWAIT_OCR),
        # await_ocr: OCR persisted -> confirm.
        (WorkflowStep.AWAIT_OCR, WorkflowStep.CONFIRM),
        # confirm: customer confirms identifiers -> identify.
        (WorkflowStep.CONFIRM, WorkflowStep.IDENTIFY),
        # identify: resolved -> search; missing/conflicting -> clarify.
        (WorkflowStep.IDENTIFY, WorkflowStep.SEARCH),
        (WorkflowStep.IDENTIFY, WorkflowStep.CLARIFY),
        # clarify: a new accepted answer re-enters at intake or identify.
        (WorkflowStep.CLARIFY, WorkflowStep.INTAKE),
        (WorkflowStep.CLARIFY, WorkflowStep.IDENTIFY),
        # search: unique match -> plan; close candidates -> choose; none compatible -> needs_staff.
        (WorkflowStep.SEARCH, WorkflowStep.PLAN),
        (WorkflowStep.SEARCH, WorkflowStep.CHOOSE),
        (WorkflowStep.SEARCH, WorkflowStep.NEEDS_STAFF),
        (WorkflowStep.PLAN, WorkflowStep.CLARIFY),
        # Workspace runtime (ADR 0002): an ambiguous/mismatched compatible set asks the customer
        # rather than auto-choosing; a fixture nameplate read goes straight to confirmation.
        (WorkflowStep.SEARCH, WorkflowStep.CLARIFY),
        (WorkflowStep.INTAKE, WorkflowStep.CONFIRM),
        # choose: candidate chosen -> plan.
        (WorkflowStep.CHOOSE, WorkflowStep.PLAN),
        # plan: complete/short plan -> draft; missing/stale inventory -> needs_staff.
        (WorkflowStep.PLAN, WorkflowStep.DRAFT),
        (WorkflowStep.PLAN, WorkflowStep.NEEDS_STAFF),
        # draft: slots rendered -> verify.
        (WorkflowStep.DRAFT, WorkflowStep.VERIFY),
        # verify: all checks pass -> review; any rule fails -> needs_staff.
        (WorkflowStep.VERIFY, WorkflowStep.REVIEW),
        (WorkflowStep.VERIFY, WorkflowStep.NEEDS_STAFF),
        # review: approved -> complete; (rejection/correction starts a NEW revision thread
        # handled out-of-band by approval/revisions, not an automatic edge here).
        (WorkflowStep.REVIEW, WorkflowStep.COMPLETE),
    }
)


def _item_step(item: ItemState) -> WorkflowStep | None:
    """Return the step an unresolved item requires, or ``None`` if the item is terminal.

    Order mirrors the per-item journey: a machine must be identified before search, search
    before an ambiguous choice; a configured item with candidates that still cannot be
    decided automatically is escalated rather than guessed.
    """
    if item.status == "needs_information":
        return WorkflowStep.CLARIFY
    if item.status == "unresolved":
        if item.configuration_id is None:
            return WorkflowStep.IDENTIFY
        if not item.candidate_part_ids:
            return WorkflowStep.SEARCH
        if item.selected_part_id is None and len(item.candidate_part_ids) > 1:
            return WorkflowStep.CHOOSE
        # Configured, has candidates, but not resolvable automatically: escalate.
        return WorkflowStep.NEEDS_STAFF
    return None


def next_step(state: EnquiryState) -> WorkflowStep:
    """Return the next action for ``state``. Deterministic; pure; no I/O; no LLM.

    The decision is a total function of the typed state. Given the same state the result is
    always the same value, which is exactly why the transition table is testable and why no
    model is ever consulted to pick a step.
    """
    # 0. Safety valve: an unexpected loop is handed to staff rather than cycling forever.
    if state.step_count >= MAX_STEPS:
        return WorkflowStep.NEEDS_STAFF
    # 0b. A step recorded an outcome only a person can resolve (no compatible part for any
    # item, or a failed verification gate): hand to staff instead of looping.
    if state.phase == "needs_staff":
        return WorkflowStep.NEEDS_STAFF

    # 1. Nothing extracted yet -> intake.
    if not state.items:
        return WorkflowStep.INTAKE

    # 2. Externally driven waits: a nameplate photo is being read / awaiting confirmation.
    if state.phase == "await_ocr":
        return WorkflowStep.AWAIT_OCR
    if state.phase == "confirm":
        return WorkflowStep.CONFIRM

    # 3. A pending clarifying question blocks until the customer answers.
    if state.pending_question is not None:
        return WorkflowStep.CLARIFY

    # 4. Resolve items in order; the first non-terminal item drives the step.
    for item in state.items:
        step = _item_step(item)
        if step is not None:
            return step

    # 5. Every item is terminal (ready or unavailable). Run the tail pipeline.
    any_ready = any(item.status == "ready" for item in state.items)
    if state.draft_id is None:
        if any_ready and state.phase != "planned":
            return WorkflowStep.PLAN
        return WorkflowStep.DRAFT
    if state.verification_id is None:
        return WorkflowStep.VERIFY
    if state.phase not in _REVIEWED_PHASES:
        return WorkflowStep.REVIEW
    return WorkflowStep.COMPLETE


def is_executable(step: WorkflowStep) -> bool:
    """True when the runner should dispatch ``step`` to an injected handler."""
    return step in EXECUTABLE_STEPS


def is_waiting(step: WorkflowStep) -> bool:
    """True when ``step`` suspends the run awaiting an external/human event."""
    return step in WAITING_STEPS


def is_terminal(step: WorkflowStep) -> bool:
    """True when ``step`` ends the run (approved/published or handed to staff)."""
    return step in TERMINAL_STEPS
