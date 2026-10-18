"""F28 HTTP adapter: GET /v1/enquiries/{enquiry_id}/items/{item_id}/references (200).

Returns the catalogue evidence references that back an item's selected fitment: each is a source
citation (``source_reference``) and page, flagged ``synthetic`` when it comes from the seed-42
fixture so a demo citation is never mistaken for a real document. Owner access; a foreign
enquiry/item is NOT_FOUND. Delegates to the ``f28_compatibility_references`` facade, which surfaces
a clean 503 offline.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import ReferenceList
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f28_compatibility_references as facade

router = APIRouter(tags=["search"])


@router.get(
    "/enquiries/{enquiry_id}/items/{item_id}/references",
    response_model=ReferenceList,
    status_code=200,
    operation_id="f28_list_references",
    summary="Read the catalogue evidence references backing an item's fitment",
)
async def list_references(
    enquiry_id: UUID,
    item_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> ReferenceList:
    return await facade.list_references(actor, enquiry_id, item_id, container=container)
