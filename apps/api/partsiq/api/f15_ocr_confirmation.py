"""F15 HTTP adapter: POST /v1/enquiries/{enquiry_id}/confirm-nameplate (202).

Records the HUMAN confirmation (optionally a correction) of an OCR nameplate extraction. An
unconfirmed model reading can never authorise machine matching — only this recorded confirmation
can (CONSTRAINTS rule 8); the serial is stored VERBATIM and a blank corrected serial routes to the
missing-serial flow (F15). A stale ``expected_revision`` is a 409. Mutating, so an
``Idempotency-Key`` is required. Owner access; a foreign enquiry/extraction is NOT_FOUND. The
response is the committed :class:`EnquiryView` (202). Delegates to the ``f15_ocr_confirmation``
facade, which surfaces a clean 503 offline.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.contracts import ActorContext, ConfirmExtraction, EnquiryView
from partsiq.core.dependencies import (
    AppContainer,
    get_container,
    idempotency_key,
    require_actor,
    typed_body,
)
from partsiq.features import f15_ocr_confirmation as facade

router = APIRouter(tags=["enquiries"])


@router.post(
    "/enquiries/{enquiry_id}/confirm-nameplate",
    response_model=EnquiryView,
    status_code=202,
    operation_id="f15_confirm_nameplate",
    summary="Confirm (or correct) an OCR nameplate extraction for an enquiry",
)
async def confirm_nameplate(
    enquiry_id: UUID,
    command: ConfirmExtraction = Depends(typed_body(ConfirmExtraction)),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
    key: UUID = Depends(idempotency_key),
) -> EnquiryView:
    # ``key`` enforces the Idempotency-Key header (REST_API.md); the DB-backed confirmation
    # transaction is idempotent per key once wired. The command carries the extraction id.
    _ = key
    return await facade.confirm_nameplate(actor, enquiry_id, command, container=container)
