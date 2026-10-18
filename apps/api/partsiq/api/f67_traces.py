"""F67 HTTP adapter: GET /v1/staff/enquiries/{enquiry_id}/traces (200).

Returns the redacted per-stage execution trace for an enquiry's current revision (stage, start,
duration, status, error code). Read-only. Review access; a foreign/unassigned enquiry is NOT_FOUND
and a non-staff (demo) caller is refused by the facade's role gate (403). Delegates to the
``f67_traces`` facade.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import TraceView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f67_traces as facade

router = APIRouter(tags=["staff"])


@router.get(
    "/staff/enquiries/{enquiry_id}/traces",
    response_model=TraceView,
    status_code=200,
    operation_id="f67_list_stages",
    summary="Read the per-stage execution trace for an enquiry (redacted)",
)
async def list_stages(
    enquiry_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> TraceView:
    return await facade.list_stages(actor, enquiry_id, container=container)
