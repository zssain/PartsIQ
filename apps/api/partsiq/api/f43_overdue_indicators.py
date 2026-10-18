"""F43 HTTP adapter: GET /v1/staff/enquiries/{enquiry_id}/deadline (200).

Returns the review deadline (``due_at``), the server time and whether the enquiry is overdue
(unresolved states only). Review access; a foreign/unassigned enquiry is NOT_FOUND and a non-staff
(demo) caller is refused by the facade's role gate (403). Delegates to the
``f43_overdue_indicators`` facade.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import DeadlineView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f43_overdue_indicators as facade

router = APIRouter(tags=["staff"])


@router.get(
    "/staff/enquiries/{enquiry_id}/deadline",
    response_model=DeadlineView,
    status_code=200,
    operation_id="f43_deadline",
    summary="Read the review deadline and overdue indicator for an enquiry",
)
async def deadline(
    enquiry_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> DeadlineView:
    return await facade.deadline(actor, enquiry_id, container=container)
