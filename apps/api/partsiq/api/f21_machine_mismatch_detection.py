"""F21 HTTP adapter: GET /v1/enquiries/{enquiry_id}/items/{item_id}/mismatch (200).

Returns the model/serial mismatch verdict for one enquiry item. Owner access; a foreign
enquiry/item is NOT_FOUND. Delegates to the ``f21_machine_mismatch_detection`` facade.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import MismatchView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f21_machine_mismatch_detection as facade

router = APIRouter(tags=["search"])


@router.get(
    "/enquiries/{enquiry_id}/items/{item_id}/mismatch",
    response_model=MismatchView,
    status_code=200,
    operation_id="f21_check_hints",
    summary="Read the model/serial mismatch verdict for an enquiry item",
)
async def check_hints(
    enquiry_id: UUID,
    item_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> MismatchView:
    return await facade.check_hints(actor, enquiry_id, item_id, container=container)
