"""F37 HTTP adapter: GET /v1/staff/enquiries/{enquiry_id} (200).

Returns the current review workspace snapshot (enquiry, facts, draft, verification, assignee) for
an authorized reviewer. Review access; a foreign/unassigned enquiry is NOT_FOUND and a non-staff
(demo) caller is refused by the facade's role gate (403). Delegates to the ``f37_review_workspace``
facade.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import ReviewView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f37_review_workspace as facade

router = APIRouter(tags=["staff"])


@router.get(
    "/staff/enquiries/{enquiry_id}",
    response_model=ReviewView,
    status_code=200,
    operation_id="f37_get_workspace",
    summary="Read the review workspace snapshot for an enquiry",
)
async def get_workspace(
    enquiry_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> ReviewView:
    return await facade.get_workspace(actor, enquiry_id, container=container)
