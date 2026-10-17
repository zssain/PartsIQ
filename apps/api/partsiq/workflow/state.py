"""Workflow state: construction, durable thread keys, merge helpers and conversation memory.

The durable state IS the typed :class:`EnquiryState` contract (items keyed by item UUID,
revision, session generation, catalogue version, pending question, draft/verification ids,
phase). The checkpoint thread key includes the enquiry id AND the active revision, so events
for an old revision resume a DIFFERENT thread and cannot mutate current data (F50).

Conversation memory (F12) is accumulated here: prior confirmed facts (model/serial) and the
retained message history are carried forward across steps as a typed
:class:`ExtractionContext`, so a run resumes by enquiry/revision with its compacted facts
intact and never mixes customer sessions. Ported from the earlier build's
``services/orchestrator/app/state.py`` (plus the memory carried through its intake specialist
context); the LangGraph checkpoint wrapper is discarded — persistence lives in
:mod:`partsiq.workflow.repository`.
"""
from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from partsiq.core.api_models import ExtractionContext
from partsiq.core.contracts import EnquiryState, ItemState, MessageView

__all__ = [
    "EnquiryState",
    "ItemState",
    "thread_id",
    "new_state",
    "advance",
    "apply_outcome_state",
    "reset_derived_state",
    "carry_forward_memory",
]


def thread_id(enquiry_id: UUID, revision: int) -> str:
    """Durable checkpoint thread key: per enquiry AND per active revision (F12/F50).

    Two revisions of the same enquiry produce distinct keys, so a resumed run of an old
    revision cannot overwrite the current one.
    """
    return f"enquiry:{enquiry_id}:rev:{revision}"


def new_state(
    enquiry_id: UUID,
    revision: int,
    *,
    session_generation: int | None = None,
    catalogue_version_id: UUID | None = None,
    items: Sequence[ItemState] | None = None,
    phase: str = "",
) -> EnquiryState:
    """Build a fresh :class:`EnquiryState` at the start of a (enquiry, revision) run."""
    return EnquiryState(
        enquiry_id=enquiry_id,
        revision=revision,
        session_generation=session_generation,
        catalogue_version_id=catalogue_version_id,
        items=list(items) if items is not None else [],
        step_count=0,
        pending_question=None,
        draft_id=None,
        verification_id=None,
        phase=phase,
    )


def advance(state: EnquiryState) -> EnquiryState:
    """Return a copy with the bounded transition counter incremented by one.

    The runner increments the counter once per executed step; the transition table's safety
    valve escalates to staff once it reaches ``MAX_STEPS``.
    """
    return state.model_copy(update={"step_count": state.step_count + 1})


def apply_outcome_state(state: EnquiryState, updates: dict[str, object]) -> EnquiryState:
    """Merge a handler's typed state updates into ``state`` without mutating the original.

    Only known :class:`EnquiryState` fields are accepted (the contract forbids extras), so a
    handler cannot smuggle arbitrary keys into the durable state.
    """
    return state.model_copy(update=updates)


def reset_derived_state(state: EnquiryState) -> EnquiryState:
    """Clear everything DERIVED from prior facts and re-enter the pipeline (F38).

    A correction invalidates the draft, the verification and any pending question, so
    recomputation starts again. Approval/publication is never carried across a correction;
    the caller increments the revision separately (which also changes the thread key).
    """
    return state.model_copy(
        update={
            "draft_id": None,
            "verification_id": None,
            "pending_question": None,
            "phase": "intake",
        }
    )


def carry_forward_memory(
    state: EnquiryState,
    messages: Sequence[MessageView],
    *,
    confirmed_model: str | None = None,
    confirmed_serial: str | None = None,
) -> ExtractionContext:
    """Accumulate conversation memory for the current (enquiry, revision) run (F12).

    Prior confirmed facts (a human-confirmed model/serial) and the retained message history
    are compacted into a typed :class:`ExtractionContext` bound to THIS enquiry and revision.
    Only messages for the current enquiry are retained — a foreign thread's messages are
    dropped, never mixed into another customer's context. The result is the exact memory a
    later step (extraction/resolution) receives when a run resumes.
    """
    retained = [m for m in messages if m.enquiry_id == state.enquiry_id]
    return ExtractionContext(
        enquiry_id=state.enquiry_id,
        revision=state.revision,
        messages=retained,
        confirmed_model=confirmed_model,
        confirmed_serial=confirmed_serial,
    )
