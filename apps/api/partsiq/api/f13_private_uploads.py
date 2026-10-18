"""F13 HTTP adapter: POST /v1/enquiries/{enquiry_id}/uploads (200) and
GET /v1/enquiries/{enquiry_id}/attachments (200).

POST mints a short-lived signed upload ticket for a nameplate photo; GET lists the enquiry's
attachments. Owner access; a foreign enquiry is NOT_FOUND. The ``UploadRequest`` carries its own
``enquiry_id``; the path id is authoritative and a mismatch is rejected (MALFORMED_REQUEST).
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import AttachmentList
from partsiq.core.contracts import ActorContext, UploadRequest, UploadTicket
from partsiq.core.dependencies import (
    AppContainer,
    get_container,
    require_actor,
    typed_body,
)
from partsiq.core.errors import PartsIQError
from partsiq.features import f13_private_uploads as facade

router = APIRouter(tags=["enquiries"])


@router.post(
    "/enquiries/{enquiry_id}/uploads",
    response_model=UploadTicket,
    status_code=200,
    operation_id="f13_create_upload",
    summary="Mint a signed upload ticket for a nameplate photo",
)
async def create_upload(
    enquiry_id: UUID,
    command: UploadRequest = Depends(typed_body(UploadRequest)),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> UploadTicket:
    if command.enquiry_id != enquiry_id:
        raise PartsIQError(
            "MALFORMED_REQUEST", internal_detail="path enquiry_id does not match body"
        )
    return await facade.create(actor, command, container=container)


@router.get(
    "/enquiries/{enquiry_id}/attachments",
    response_model=AttachmentList,
    status_code=200,
    operation_id="f13_list_attachments",
    summary="List the caller's enquiry attachments",
)
async def list_attachments(
    enquiry_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> AttachmentList:
    return await facade.list_attachments(actor, enquiry_id, container=container)
