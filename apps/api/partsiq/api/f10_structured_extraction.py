"""F10 HTTP adapter: GET /v1/enquiries/{enquiry_id}/extraction (200).

Returns the current structured extraction for the caller's own enquiry (owner access). A foreign
or stale-session enquiry is NOT_FOUND.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import ExtractionView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f10_structured_extraction as facade

router = APIRouter(tags=["enquiries"])


@router.get(
    "/enquiries/{enquiry_id}/extraction",
    response_model=ExtractionView,
    status_code=200,
    operation_id="f10_read_current",
    summary="Read the current extraction for the caller's enquiry",
)
async def read_current(
    enquiry_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> ExtractionView:
    return await facade.read_current(actor, enquiry_id, container=container)
