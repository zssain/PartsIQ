"""F51 HTTP adapter: GET /v1/jobs/{job_id} (200).

Returns the status of a single background job (state, kind, attempts, error code, resource id).
Read-only. Scoped access: the store authorises the caller against the job's owning resource, so a
foreign job is NOT_FOUND (404). Delegates to the ``f51_background_jobs`` facade, which surfaces a
clean 503 offline.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import JobView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f51_background_jobs as facade

router = APIRouter(tags=["jobs"])


@router.get(
    "/jobs/{job_id}",
    response_model=JobView,
    status_code=200,
    operation_id="f51_get_status",
    summary="Read the status of a background job the caller owns",
)
async def get_status(
    job_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> JobView:
    return await facade.get_status(actor, job_id, container=container)
