"""F52 HTTP adapter: POST /v1/jobs/{job_id}/retry (202).

Re-queues a FAILED background job (failed-only; a non-failed job is a 409) and returns the job
handle. The body is :class:`RetryRequest` (``expected_revision``) and the request carries an
``Idempotency-Key``; a stale revision is a 409 and a duplicate submit re-queues once. Scoped
access: a foreign job is NOT_FOUND (404). Delegates to the ``f52_retry_and_dedup`` facade, which
surfaces a clean 503 offline.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import JobView, RetryRequest
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import (
    AppContainer,
    get_container,
    idempotency_key,
    require_actor,
    typed_body,
)
from partsiq.features import f52_retry_and_dedup as facade

router = APIRouter(tags=["jobs"])


@router.post(
    "/jobs/{job_id}/retry",
    response_model=JobView,
    status_code=202,
    operation_id="f52_retry_failed",
    summary="Re-queue a failed background job (failed-only, revision-checked, deduped)",
)
async def retry_failed(
    job_id: UUID,
    request: RetryRequest = Depends(typed_body(RetryRequest)),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
    key: UUID = Depends(idempotency_key),
) -> JobView:
    return await facade.retry_failed(actor, job_id, request, key, container=container)
