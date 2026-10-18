"""F39 HTTP adapters: POST /v1/staff/enquiries/{enquiry_id}/approve (200) and
POST /v1/staff/enquiries/{enquiry_id}/reject (200).

``approve`` publishes the single recommendation for the current, verified draft (the human
publication gate); ``reject`` records a reason and never publishes. Both are mutating and carry an
``Idempotency-Key``. Review access; a foreign/unassigned enquiry is NOT_FOUND and a non-staff
(demo) caller is refused by the facade's role gate (403). The path ``enquiry_id`` must match the
body's ``enquiry_id`` (a mismatch is a 422). Delegates to the ``f39_review_actions`` facade.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.contracts import (
    ActorContext,
    ApprovalRequest,
    ApprovalResult,
    RejectionRequest,
    ReviewResult,
)
from partsiq.core.dependencies import (
    AppContainer,
    get_container,
    idempotency_key,
    require_actor,
    typed_body,
)
from partsiq.core.errors import PartsIQError
from partsiq.features import f39_review_actions as facade

router = APIRouter(tags=["staff"])


def _require_path_matches_body(path_enquiry_id: UUID, body_enquiry_id: UUID) -> None:
    """Reject a request whose body targets a different enquiry than the path (422)."""
    if path_enquiry_id != body_enquiry_id:
        raise PartsIQError(
            "VALIDATION_FAILED",
            detail="One or more fields are invalid.",
            internal_detail="path enquiry_id does not match the request body",
        )


@router.post(
    "/staff/enquiries/{enquiry_id}/approve",
    response_model=ApprovalResult,
    status_code=200,
    operation_id="f39_approve",
    summary="Approve a reviewed draft and publish the single recommendation",
)
async def approve(
    enquiry_id: UUID,
    request: ApprovalRequest = Depends(typed_body(ApprovalRequest)),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
    key: UUID = Depends(idempotency_key),
) -> ApprovalResult:
    _require_path_matches_body(enquiry_id, request.enquiry_id)
    return await facade.approve(actor, request, key, container=container)


@router.post(
    "/staff/enquiries/{enquiry_id}/reject",
    response_model=ReviewResult,
    status_code=200,
    operation_id="f39_reject",
    summary="Reject a reviewed draft (records a reason; never publishes)",
)
async def reject(
    enquiry_id: UUID,
    request: RejectionRequest = Depends(typed_body(RejectionRequest)),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
    key: UUID = Depends(idempotency_key),
) -> ReviewResult:
    _require_path_matches_body(enquiry_id, request.enquiry_id)
    return await facade.reject(actor, request, key, container=container)
