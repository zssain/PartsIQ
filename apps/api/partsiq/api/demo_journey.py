"""Demo-journey HTTP adapters: the progress timeline and the in-demo review approval.

These close the fixture demo loop over the real LangGraph run:

* ``GET /v1/enquiries/{enquiry_id}/timeline`` — the ordered, persisted workflow progress events
  (step, human label, timestamp, status) the customer progress bar and the staff specialist
  timeline animate through. Concise step evidence, never hidden model chain-of-thought.
* ``POST /v1/enquiries/{enquiry_id}/approve`` — the human-review approval. In the demo the caller
  reviews and approves its OWN session's enquiry (F03 demo role switching is presentational;
  data stays session-scoped), publishing exactly one recommendation reply. Idempotent: a repeat
  approval never publishes a duplicate. In DB mode staff approval goes through the role-gated
  ``/v1/staff/enquiries/{id}/approve`` instead; this route operates on the fixture journey.

Owner/own-demo-session access only; a foreign or stale-session enquiry is NOT_FOUND.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from partsiq.core.contracts import ActorContext, EnquiryView
from partsiq.core.dependencies import AppContainer, get_container, require_actor

router = APIRouter(tags=["enquiries"])


class ProgressEventView(BaseModel):
    step: str
    label: str
    at: datetime
    status: str


class ProgressTimeline(BaseModel):
    enquiry_id: UUID
    events: list[ProgressEventView]


@router.get(
    "/enquiries/{enquiry_id}/timeline",
    response_model=ProgressTimeline,
    status_code=200,
    operation_id="demo_read_timeline",
    summary="Ordered workflow progress events for the caller's enquiry",
)
async def read_timeline(
    enquiry_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> ProgressTimeline:
    journey = container.require_journey()
    events = await journey.timeline(actor, enquiry_id)
    return ProgressTimeline(
        enquiry_id=enquiry_id,
        events=[ProgressEventView(**event) for event in events],
    )


@router.post(
    "/enquiries/{enquiry_id}/approve",
    response_model=EnquiryView,
    status_code=200,
    operation_id="demo_approve_enquiry",
    summary="Approve the enquiry at the human-review gate (demo review)",
)
async def approve_enquiry(
    enquiry_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> EnquiryView:
    journey = container.require_journey()
    return await journey.approve_fixture(actor, enquiry_id)
