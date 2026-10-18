"""F33 HTTP adapter: GET /v1/enquiries/{enquiry_id}/plan (200).

Returns the fulfilment PLAN for a whole enquiry: for every ready item, the warehouse allocations
(local-first, then nearest by integer transfer lead time) and any explicit shortage, plus the
stock snapshot id the plan rested on. This is a RECOMMENDATION only — it never reserves stock and
never creates an order (F33). Review access; a foreign enquiry is NOT_FOUND. Delegates to the
``f33_fulfilment_planning`` facade, which surfaces a clean 503 offline.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import PlanView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f33_fulfilment_planning as facade

router = APIRouter(tags=["fulfilment"])


@router.get(
    "/enquiries/{enquiry_id}/plan",
    response_model=PlanView,
    status_code=200,
    operation_id="f33_plan_enquiry",
    summary="Read the fulfilment plan (allocations + shortage) for the whole enquiry",
)
async def plan_enquiry(
    enquiry_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> PlanView:
    return await facade.plan_enquiry(actor, enquiry_id, container=container)
