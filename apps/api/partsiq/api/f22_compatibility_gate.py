"""F22 HTTP adapter: GET /v1/enquiries/{enquiry_id}/items/{item_id}/compatibility (200).

Returns the catalogue-derived compatible part set for one item's resolved configuration. Review
access; a foreign enquiry/item is NOT_FOUND. Delegates to the ``f22_compatibility_gate`` facade.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import CompatibilityView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f22_compatibility_gate as facade

router = APIRouter(tags=["search"])


@router.get(
    "/enquiries/{enquiry_id}/items/{item_id}/compatibility",
    response_model=CompatibilityView,
    status_code=200,
    operation_id="f22_compatible_set",
    summary="Read the compatible part set for an enquiry item's configuration",
)
async def compatible_set(
    enquiry_id: UUID,
    item_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> CompatibilityView:
    return await facade.compatible_set(actor, enquiry_id, item_id, container=container)
