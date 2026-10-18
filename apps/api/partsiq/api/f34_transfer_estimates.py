"""F34 HTTP adapter: GET /v1/enquiries/{enquiry_id}/transfers (200).

Returns the inter-warehouse transfer routes a plan may use for an enquiry: each row carries the
integer ``transfer_days`` from the stored route, or ``None`` when no route exists (a missing route
is surfaced as unavailable, never an invented promise — F34). ``estimate_only`` is always True.
Review access; a foreign enquiry is NOT_FOUND. Delegates to the ``f34_transfer_estimates`` facade,
which surfaces a clean 503 offline.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import TransferView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f34_transfer_estimates as facade

router = APIRouter(tags=["fulfilment"])


@router.get(
    "/enquiries/{enquiry_id}/transfers",
    response_model=TransferView,
    status_code=200,
    operation_id="f34_transfer_evidence",
    summary="Read the transfer-route estimates available to the enquiry's plan",
)
async def transfer_evidence(
    enquiry_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> TransferView:
    return await facade.transfer_evidence(actor, enquiry_id, container=container)
