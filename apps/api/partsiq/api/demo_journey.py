"""Demo-journey HTTP adapter: the workflow progress timeline.

``GET /v1/enquiries/{enquiry_id}/timeline`` returns the ordered, persisted workflow progress
events (step, human label, timestamp, status) the customer progress bar and the staff specialist
timeline animate through — concise step evidence, never hidden model chain-of-thought.

The human-review APPROVAL is NOT a separate route here (F03: no redundant endpoint). In the demo
the reviewer is the same anonymous session; approval/rejection go through the CANONICAL review
endpoints ``POST /v1/staff/enquiries/{id}/approve`` and ``/reject``, which the fixture journey
serves under own-demo-session scope. Owner/own-demo-session access only; a foreign or stale-session
enquiry is NOT_FOUND.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor

router = APIRouter(tags=["enquiries"])


class ProgressEventView(BaseModel):
    step: str
    label: str
    at: datetime
    status: str
    # Concise evidence line recorded when the step ran (never hidden reasoning).
    detail: str | None = None


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
