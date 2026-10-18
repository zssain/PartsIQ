"""F40 HTTP adapter: GET /v1/staff/enquiries/{enquiry_id}/approval-state (200).

Returns the current approval binding for an enquiry: whether an approval exists, its decision and
bound fact hash, and whether a later correction has INVALIDATED it. Read-only. Review access; a
foreign/unassigned enquiry is NOT_FOUND and a non-staff (demo) caller is refused by the facade's
role gate (403). Delegates to the ``f40_approval_invalidation`` facade.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import ApprovalState
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f40_approval_invalidation as facade

router = APIRouter(tags=["staff"])


@router.get(
    "/staff/enquiries/{enquiry_id}/approval-state",
    response_model=ApprovalState,
    status_code=200,
    operation_id="f40_read_binding",
    summary="Read the current approval binding (and whether it has been invalidated)",
)
async def read_binding(
    enquiry_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> ApprovalState:
    return await facade.read_binding(actor, enquiry_id, container=container)
