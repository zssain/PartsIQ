"""F11 HTTP adapter: POST /v1/enquiries/{enquiry_id}/messages (202).

Appends a customer message under ``expected_revision`` (a stale revision is 409). Owner access;
a foreign enquiry is NOT_FOUND. Every mutating request carries an ``Idempotency-Key``.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.contracts import ActorContext, EnquiryView, MessageCreate
from partsiq.core.dependencies import (
    AppContainer,
    get_container,
    idempotency_key,
    require_actor,
    typed_body,
)
from partsiq.features import f11_clarifying_questions as facade

router = APIRouter(tags=["enquiries"])


@router.post(
    "/enquiries/{enquiry_id}/messages",
    response_model=EnquiryView,
    status_code=202,
    operation_id="f11_append_message",
    summary="Append a customer message (bumps revision; 202)",
)
async def append_message(
    enquiry_id: UUID,
    command: MessageCreate = Depends(typed_body(MessageCreate)),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
    key: UUID = Depends(idempotency_key),
) -> EnquiryView:
    return await facade.append(actor, enquiry_id, command, key, container=container)
