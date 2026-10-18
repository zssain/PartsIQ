"""F41 HTTP adapters: POST /v1/staff/enquiries/{enquiry_id}/notes (201) and
GET /v1/staff/enquiries/{enquiry_id}/notes (200).

Append-only reviewer notes visible ONLY in the staff workspace — never in a customer response or
the approved PDF. POST appends one note (body 1..4000 chars, validated by ``NoteCreate``) and
carries an ``Idempotency-Key``; GET lists notes keyset-paged. Review access; a foreign/unassigned
enquiry is NOT_FOUND and a non-staff (demo) caller is refused by the facade's role gate (403).
Delegates to the ``f41_internal_notes`` facade.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from partsiq.core.api_models import NoteCreate, NotePage, NoteView, PageQuery
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import (
    AppContainer,
    get_container,
    idempotency_key,
    require_actor,
    typed_body,
)
from partsiq.features import f41_internal_notes as facade

router = APIRouter(tags=["staff"])


@router.post(
    "/staff/enquiries/{enquiry_id}/notes",
    response_model=NoteView,
    status_code=201,
    operation_id="f41_append_note",
    summary="Append an internal reviewer note (append-only; staff-only)",
)
async def append_note(
    enquiry_id: UUID,
    command: NoteCreate = Depends(typed_body(NoteCreate)),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
    key: UUID = Depends(idempotency_key),
) -> NoteView:
    return await facade.append_note(
        actor, enquiry_id, command.body, key, container=container
    )


@router.get(
    "/staff/enquiries/{enquiry_id}/notes",
    response_model=NotePage,
    status_code=200,
    operation_id="f41_list_notes",
    summary="List the internal reviewer notes for an enquiry (paginated)",
)
async def list_notes(
    enquiry_id: UUID,
    limit: int = Query(default=25, ge=1, le=100),
    cursor: str | None = Query(default=None),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> NotePage:
    query = PageQuery(cursor=cursor, limit=limit)
    return await facade.list_notes(actor, enquiry_id, query, container=container)
