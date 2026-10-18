"""F50 HTTP adapter: GET /v1/staff/enquiries/{enquiry_id}/workflow (200).

Returns the durable workflow state for an enquiry (current step, completed steps, pending job id,
error code). Read-only. Review access; a foreign/unassigned enquiry is NOT_FOUND and a non-staff
(demo) caller is refused by the facade's role gate (403). Delegates to the ``f50_durable_workflows``
facade.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import WorkflowView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f50_durable_workflows as facade

router = APIRouter(tags=["staff"])


@router.get(
    "/staff/enquiries/{enquiry_id}/workflow",
    response_model=WorkflowView,
    status_code=200,
    operation_id="f50_inspect_run",
    summary="Inspect the durable workflow state for an enquiry",
)
async def inspect_run(
    enquiry_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> WorkflowView:
    return await facade.inspect_run(actor, enquiry_id, container=container)
