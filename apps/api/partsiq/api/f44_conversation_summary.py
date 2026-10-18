"""F44 HTTP adapters: POST /v1/staff/enquiries/{enquiry_id}/summary (202) and
GET /v1/staff/enquiries/{enquiry_id}/summary (200).

``enqueue_summary`` queues a durable background job to summarise the conversation at the given
revision (never runs the model inline) and returns the job handle (202); it carries an
``Idempotency-Key`` so a double submit enqueues once. ``read_summary`` returns the stored summary
and whether it is stale (200). Review access; a foreign/unassigned enquiry is NOT_FOUND and a
non-staff (demo) caller is refused by the facade's role gate (403). Delegates to the
``f44_conversation_summary`` facade.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import JobView, RevisionOnly, SummaryView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import (
    AppContainer,
    get_container,
    idempotency_key,
    require_actor,
    typed_body,
)
from partsiq.features import f44_conversation_summary as facade

router = APIRouter(tags=["staff"])


@router.post(
    "/staff/enquiries/{enquiry_id}/summary",
    response_model=JobView,
    status_code=202,
    operation_id="f44_enqueue_summary",
    summary="Queue a background conversation-summary job for an enquiry revision",
)
async def enqueue_summary(
    enquiry_id: UUID,
    request: RevisionOnly = Depends(typed_body(RevisionOnly)),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
    key: UUID = Depends(idempotency_key),
) -> JobView:
    return await facade.enqueue_summary(actor, enquiry_id, request, key, container=container)


@router.get(
    "/staff/enquiries/{enquiry_id}/summary",
    response_model=SummaryView,
    status_code=200,
    operation_id="f44_read_summary",
    summary="Read the stored conversation summary (and whether it is stale)",
)
async def read_summary(
    enquiry_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> SummaryView:
    return await facade.read_summary(actor, enquiry_id, container=container)
