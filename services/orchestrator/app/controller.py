"""Deterministic workflow controller.

Contract: ``def next_step(state: EnquiryState) -> WorkflowStep``.

The transition is pure, ordered and rule-based — NOT model-driven (ADR-003). Missing
serials, verification failures and approval gates are decided here in code so they are
testable on labelled cases and cannot be overridden by an LLM. Blocking steps
(await_ocr, confirm, clarify, review) are graph interrupts, not specialist functions.
"""
from __future__ import annotations

from partsiq_common.contracts import EnquiryState, WorkflowStep

# Bounded transition count before handing to staff (WORKFLOW_MAX_STEPS, spec/environment.json).
MAX_STEPS = 12
# Phases that mean a prior human/approval decision is recorded; review is complete.
_REVIEWED_PHASES = frozenset({"reviewed", "approved", "complete"})


def next_step(state: EnquiryState) -> WorkflowStep:
    """Return the next action. Evaluated top-to-bottom; the first matching rule wins."""
    # 0. Safety valve: never loop forever.
    if state.step_count >= MAX_STEPS:
        return WorkflowStep.NEEDS_STAFF

    # 1. Nothing extracted yet.
    if not state.items:
        return WorkflowStep.INTAKE

    # 2. Externally-driven waits (a nameplate photo is being read / awaiting confirmation).
    if state.phase == "await_ocr":
        return WorkflowStep.AWAIT_OCR
    if state.phase == "confirm":
        return WorkflowStep.CONFIRM

    # 3. A pending clarifying question blocks until the customer answers.
    if state.pending_question is not None:
        return WorkflowStep.CLARIFY

    # 4. Resolve items in order; the first unresolved item drives the step.
    for item in state.items:
        if item.status == "needs_information":
            return WorkflowStep.CLARIFY
        if item.status == "unresolved":
            if item.configuration_id is None:
                return WorkflowStep.IDENTIFY
            if not item.candidate_part_ids:
                return WorkflowStep.SEARCH
            if item.selected_part_id is None and len(item.candidate_part_ids) > 1:
                return WorkflowStep.CHOOSE
            # A configured item with candidates but still unresolved cannot be decided
            # automatically; escalate rather than guess.
            return WorkflowStep.NEEDS_STAFF

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
