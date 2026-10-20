"""F09 HTTP adapter: POST /v1/enquiries (202) and GET /v1/enquiries/{enquiry_id} (200).

POST commits a new enquiry + first message in one in-memory transaction and returns the committed
view without waiting for background identification (202). GET returns the caller's own enquiry; a
foreign one is NOT_FOUND. Every mutating request carries an ``Idempotency-Key``.
"""
from __future__ import annotations

from uuid import UUID

from typing import Literal

from fastapi import APIRouter, Depends, Query

from partsiq.core.contracts import ActorContext, EnquiryCreate, EnquiryView
from partsiq.core.dependencies import (
    AppContainer,
    get_container,
    idempotency_key,
    require_actor,
    typed_body,
)
from partsiq.features import f09_bilingual_chat as facade

router = APIRouter(tags=["enquiries"])


@router.post(
    "/enquiries",
    response_model=EnquiryView,
    status_code=202,
    operation_id="f09_create_enquiry",
    summary="Create an enquiry (commits a durable workflow job; 202)",
)
async def create_enquiry(
    command: EnquiryCreate = Depends(typed_body(EnquiryCreate)),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
    key: UUID = Depends(idempotency_key),
    mode: Literal["guided", "collaboration"] = Query(default="guided"),
) -> EnquiryView:
    # The execution mode is chosen before the run starts (ADR 0002); it rides a request-scoped
    # context variable so the existing intake contract (EnquiryCreate) is unchanged.
    from partsiq.workspace.runtime import requested_mode

    token = requested_mode.set(mode)
    try:
        return await facade.create(actor, command, key, container=container)
    finally:
        requested_mode.reset(token)


@router.get(
    "/enquiries/{enquiry_id}",
    response_model=EnquiryView,
    status_code=200,
    operation_id="f09_get_enquiry",
    summary="Read the caller's own enquiry",
)
async def get_enquiry(
    enquiry_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> EnquiryView:
    return await facade.get_enquiry(actor, enquiry_id, container=container)
