"""F18 HTTP adapter: GET /v1/enquiries/{enquiry_id}/progress (200).

Returns the caller's own enquiry workflow progress (step, wait reason, revision, timestamp).
Owner access; a foreign enquiry is NOT_FOUND.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import ProgressView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f18_progress_timeline as facade

router = APIRouter(tags=["enquiries"])


@router.get(
    "/enquiries/{enquiry_id}/progress",
    response_model=ProgressView,
    status_code=200,
    operation_id="f18_read_progress",
    summary="Read the caller's enquiry workflow progress",
)
async def read_progress(
    enquiry_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> ProgressView:
    return await facade.read_progress(actor, enquiry_id, container=container)
