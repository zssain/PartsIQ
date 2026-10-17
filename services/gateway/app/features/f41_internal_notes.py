"""F41 Internal notes (owner: gateway; depends on 03, 07, 20).

Append-only reviewer notes carrying author + timestamp, visible ONLY in the staff workspace.
They are never included in a customer-facing response or the approved PDF (the customer
EnquiryView has no notes field and the PDF template renders only verified facts). Only the
assigned reviewer (or own-session demo reviewer) may read/append; an empty or over-4000-char
note is rejected; writes are idempotent. Rendered content is escaped in the UI (React).

Pure over an injected NotesRepository; the live append-only Postgres adapter is BLOCKED.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from partsiq_common.contracts import ActorContext, Contract
from partsiq_common.errors import PartsIQError

MAX_NOTE = 4000


class F41Request(Contract):
    enquiry_id: UUID
    body: str
    idempotency_key: UUID


class F41Result(Contract):
    id: UUID
    author_id: UUID
    body: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Note:
    id: UUID
    author_id: UUID
    body: str
    created_at: datetime


class NotesRepository(Protocol):
    async def is_assigned(self, actor: ActorContext, enquiry_id: UUID) -> bool:
        """True for the assigned reviewer or the own-session demo reviewer."""
        ...

    async def append(self, actor: ActorContext, enquiry_id: UUID, body: str, idempotency_key: UUID) -> Note:
        """Append-only insert; idempotent on the key."""
        ...

    async def list_notes(self, actor: ActorContext, enquiry_id: UUID) -> list[Note]:
        """Notes in created_at/id order."""
        ...


def _validate_body(body: str) -> None:
    if not body.strip():
        raise PartsIQError("VALIDATION_FAILED", internal_detail="note must not be empty")
    if len(body) > MAX_NOTE:
        raise PartsIQError("VALIDATION_FAILED", internal_detail=f"note must be at most {MAX_NOTE} characters")


def _result(note: Note) -> F41Result:
    return F41Result(id=note.id, author_id=note.author_id, body=note.body, created_at=note.created_at)


async def append_note(actor: ActorContext, request: F41Request, *, repo: NotesRepository) -> F41Result:
    """Append a staff note (author + timestamp); assigned-only; append-only; idempotent."""
    _validate_body(request.body)
    if not await repo.is_assigned(actor, request.enquiry_id):
        raise PartsIQError("NOT_FOUND", internal_detail="enquiry not assigned to this actor")
    note = await repo.append(actor, request.enquiry_id, request.body, request.idempotency_key)
    return _result(note)


async def list_notes(actor: ActorContext, enquiry_id: UUID, *, repo: NotesRepository) -> list[F41Result]:
    """List staff notes for an enquiry (assigned-only), in created_at/id order."""
    if not await repo.is_assigned(actor, enquiry_id):
        raise PartsIQError("NOT_FOUND", internal_detail="enquiry not assigned to this actor")
    return [_result(note) for note in await repo.list_notes(actor, enquiry_id)]
