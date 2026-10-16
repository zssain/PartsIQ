"""Workflow state and thread keys.

The LangGraph state IS the typed EnquiryState contract (items keyed by item UUID,
revision, session generation, catalogue version, pending question, draft/verification
ids, phase). The durable thread key includes the enquiry id AND the active revision, so
events for an old revision resume a different thread and cannot mutate current data
(F50).
"""
from __future__ import annotations

from uuid import UUID

from partsiq_common.contracts import EnquiryState, ItemState

__all__ = ["EnquiryState", "ItemState", "thread_id", "advance"]


def thread_id(enquiry_id: UUID, revision: int) -> str:
    """Durable checkpoint thread key: per enquiry AND per active revision."""
    return f"enquiry:{enquiry_id}:rev:{revision}"


def advance(state: EnquiryState) -> EnquiryState:
    """Return a copy with the transition counter incremented (bounded by the controller)."""
    return state.model_copy(update={"step_count": state.step_count + 1})
