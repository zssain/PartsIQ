"""F38 HTTP adapter: PATCH /v1/staff/enquiries/{enquiry_id}/extraction (200).

A reviewer corrects the extracted facts for an enquiry's items; the correction opens a NEW
compatibility revision and re-runs matching/verification — it never publishes and never approves.
The body is :class:`RevisionRequest` and the request carries an ``Idempotency-Key`` (a double
submit applies once). The path ``enquiry_id`` must match the body (a mismatch is a 422). Review
access; a foreign/unassigned enquiry is NOT_FOUND and a non-staff (demo) caller is refused by the
facade's role gate (403). Delegates to the ``f38_correct_extracted_details`` facade.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.contracts import ActorContext, EnquiryView, RevisionRequest
from partsiq.core.dependencies import (
    AppContainer,
    get_container,
    idempotency_key,
    require_actor,
    typed_body,
)
from partsiq.core.errors import PartsIQError
from partsiq.features import f38_correct_extracted_details as facade

router = APIRouter(tags=["staff"])


@router.patch(
    "/staff/enquiries/{enquiry_id}/extraction",
    response_model=EnquiryView,
    status_code=200,
    operation_id="f38_correct_extraction",
    summary="Correct the extracted facts for an enquiry (opens a new revision; never publishes)",
)
async def correct_extraction(
    enquiry_id: UUID,
    request: RevisionRequest = Depends(typed_body(RevisionRequest)),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
    key: UUID = Depends(idempotency_key),
) -> EnquiryView:
    if enquiry_id != request.enquiry_id:
        raise PartsIQError(
            "VALIDATION_FAILED",
            detail="One or more fields are invalid.",
            internal_detail="path enquiry_id does not match the request body",
        )
    return await facade.correct_extraction(actor, request, key, container=container)
