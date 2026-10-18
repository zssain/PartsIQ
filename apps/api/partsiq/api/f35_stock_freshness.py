"""F35 HTTP adapter: GET /v1/enquiries/{enquiry_id}/stock-freshness (200).

Reports whether the enquiry's planned stock snapshot is still FRESH: ``fresh`` is True only when
the snapshot is neither in the future nor older than ``max_age_seconds`` and still covers the
planned allocations; otherwise ``fresh`` is False with a ``reason_code`` so a stale snapshot never
becomes a silent delivery guarantee (F35). Review access; a foreign enquiry is NOT_FOUND. Delegates
to the ``f35_stock_freshness`` facade, which surfaces a clean 503 offline.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import FreshnessView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f35_stock_freshness as facade

router = APIRouter(tags=["fulfilment"])


@router.get(
    "/enquiries/{enquiry_id}/stock-freshness",
    response_model=FreshnessView,
    status_code=200,
    operation_id="f35_check_freshness",
    summary="Report whether the enquiry's planned stock snapshot is still fresh",
)
async def check_freshness(
    enquiry_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> FreshnessView:
    return await facade.check_freshness(actor, enquiry_id, container=container)
