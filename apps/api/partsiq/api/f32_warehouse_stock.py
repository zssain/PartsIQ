"""F32 HTTP adapter: GET /v1/enquiries/{enquiry_id}/items/{item_id}/stock (200).

Returns per-warehouse netted stock for an item's SELECTED part: each row is the already-netted
available (on-hand minus reserved, a negative clamped to zero), with the snapshot id and a
``stale`` flag. A reading is NEVER a reservation (F33). Review access; a foreign enquiry/item is
NOT_FOUND. Delegates to the ``f32_warehouse_stock`` facade, which surfaces a clean 503 offline.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import StockView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f32_warehouse_stock as facade

router = APIRouter(tags=["fulfilment"])


@router.get(
    "/enquiries/{enquiry_id}/items/{item_id}/stock",
    response_model=StockView,
    status_code=200,
    operation_id="f32_stock_for_selection",
    summary="Read per-warehouse netted stock for an item's selected part",
)
async def stock_for_selection(
    enquiry_id: UUID,
    item_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> StockView:
    return await facade.stock_for_selection(actor, enquiry_id, item_id, container=container)
