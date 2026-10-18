"""F14 HTTP adapter: POST /v1/attachments/{attachment_id}/confirm-upload (202).

Confirms a finished nameplate upload (F13) and enqueues the nameplate vision job for the enquiry's
current revision; the response is the queued :class:`JobView` (202) — the OCR result is read later
through F15. The ``RevisionOnly`` body guards against confirming against a stale revision (409).
Mutating, so an ``Idempotency-Key`` is required. Owner access; a foreign attachment is NOT_FOUND.
Delegates to the ``f14_nameplate_ocr`` facade, which surfaces a clean 503 offline.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import JobView, RevisionOnly
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import (
    AppContainer,
    get_container,
    idempotency_key,
    require_actor,
    typed_body,
)
from partsiq.features import f14_nameplate_ocr as facade

router = APIRouter(tags=["enquiries"])


@router.post(
    "/attachments/{attachment_id}/confirm-upload",
    response_model=JobView,
    status_code=202,
    operation_id="f14_confirm_upload",
    summary="Confirm a finished nameplate upload and enqueue the OCR job",
)
async def confirm_upload(
    attachment_id: UUID,
    command: RevisionOnly = Depends(typed_body(RevisionOnly)),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
    key: UUID = Depends(idempotency_key),
) -> JobView:
    return await facade.confirm_upload(actor, attachment_id, command, key, container=container)
