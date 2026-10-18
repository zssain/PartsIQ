"""F61 HTTP adapters: POST /v1/enquiries/{enquiry_id}/exports (202) and
GET /v1/exports/{export_id}/download (200).

``request_pdf`` queues a durable PDF export of an APPROVED enquiry revision and returns the job
handle (202); the body is :class:`ExportRequest` (enquiry_id/revision/decision_id) and the request
carries an ``Idempotency-Key``, and the path ``enquiry_id`` must match the body (a mismatch is a
422). ``sign_download`` mints a short-lived signed URL for a finished export (200). Owner access; a
foreign resource is NOT_FOUND. Delegates to the ``f61_enquiry_pdf`` facade, which surfaces a clean
503 offline.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import JobView
from partsiq.core.contracts import ActorContext, DownloadTicket, ExportRequest
from partsiq.core.dependencies import (
    AppContainer,
    get_container,
    idempotency_key,
    require_actor,
    typed_body,
)
from partsiq.core.errors import PartsIQError
from partsiq.features import f61_enquiry_pdf as facade

router = APIRouter(tags=["exports"])


@router.post(
    "/enquiries/{enquiry_id}/exports",
    response_model=JobView,
    status_code=202,
    operation_id="f61_request_pdf",
    summary="Queue a PDF export of an approved enquiry revision",
)
async def request_pdf(
    enquiry_id: UUID,
    request: ExportRequest = Depends(typed_body(ExportRequest)),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
    key: UUID = Depends(idempotency_key),
) -> JobView:
    if enquiry_id != request.enquiry_id:
        raise PartsIQError(
            "VALIDATION_FAILED",
            detail="One or more fields are invalid.",
            internal_detail="path enquiry_id does not match the request body",
        )
    return await facade.request_pdf(actor, request, key, container=container)


@router.get(
    "/exports/{export_id}/download",
    response_model=DownloadTicket,
    status_code=200,
    operation_id="f61_sign_download",
    summary="Mint a short-lived signed download URL for a finished export",
)
async def sign_download(
    export_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> DownloadTicket:
    return await facade.sign_download(actor, export_id, container=container)
