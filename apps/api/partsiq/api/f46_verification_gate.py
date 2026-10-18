"""F46 HTTP adapter: GET /v1/staff/enquiries/{enquiry_id}/verification (200).

Returns the current verification result for an enquiry's draft (passed + any failures + bound fact
hash) — the gate the approve action is conditioned on. Read-only. Review access; a
foreign/unassigned enquiry is NOT_FOUND and a non-staff (demo) caller is refused by the facade's
role gate (403). Delegates to the ``f46_verification_gate`` facade.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.contracts import ActorContext, VerificationResult
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f46_verification_gate as facade

router = APIRouter(tags=["staff"])


@router.get(
    "/staff/enquiries/{enquiry_id}/verification",
    response_model=VerificationResult,
    status_code=200,
    operation_id="f46_read_current",
    summary="Read the verification result gating approval for an enquiry",
)
async def read_current(
    enquiry_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> VerificationResult:
    return await facade.read_current(actor, enquiry_id, container=container)
