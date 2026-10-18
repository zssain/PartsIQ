"""F20 HTTP adapter: GET /v1/enquiries/{enquiry_id}/items/{item_id}/machine (200).

Returns the resolved machine state for one enquiry item (configuration or the reason it could not
resolve). Owner access; a foreign enquiry/item is NOT_FOUND. Delegates to the
``f20_machine_identification`` facade.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import MachineView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f20_machine_identification as facade

router = APIRouter(tags=["search"])


@router.get(
    "/enquiries/{enquiry_id}/items/{item_id}/machine",
    response_model=MachineView,
    status_code=200,
    operation_id="f20_identify_machine",
    summary="Read the resolved machine configuration for an enquiry item",
)
async def identify_machine(
    enquiry_id: UUID,
    item_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> MachineView:
    return await facade.identify_machine(actor, enquiry_id, item_id, container=container)
