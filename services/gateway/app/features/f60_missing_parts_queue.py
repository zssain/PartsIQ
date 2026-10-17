"""F60 Missing-parts queue (owner: gateway; depends on 03, 20).

When the deterministic pipeline cannot resolve an item (a genuine empty search — never a
fabricated stock figure), it is recorded ONCE in a missing-parts queue linked back to its
enquiry. Assigned staff then move it through investigating -> resolved / unavailable, each with
a note; resolving REQUIRES a staff explanation. Updating status never creates catalogue rows
(no automatic catalogue creation) and never invents stock. Only the assigned reviewer may act
(foreign item -> NOT_FOUND); a stale expected_revision is a 409.

Pure over an injected MissingPartsRepository; the live Postgres adapter (RLS-scoped) is BLOCKED.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from partsiq_common.contracts import ActorContext, Contract
from partsiq_common.errors import PartsIQError

VALID_STATUSES = frozenset({"investigating", "resolved", "unavailable"})
MAX_NOTE = 2000


class MissingPartUpdateBody(Contract):
    status: str
    staff_note: str
    expected_revision: int


class F60Request(Contract):
    item_id: UUID
    status: str
    staff_note: str
    expected_revision: int


class F60Result(Contract):
    id: UUID
    status: str
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class MissingEntry:
    id: UUID
    item_id: UUID
    enquiry_id: UUID
    assigned_to: UUID | None
    status: str
    staff_note: str
    revision: int
    updated_at: datetime
    # Note: there is deliberately NO stock/availability field here — a missing part is an empty
    # result, not fabricated stock.


class MissingPartsRepository(Protocol):
    async def record(self, item_id: UUID, enquiry_id: UUID) -> MissingEntry:
        """Idempotently record an unresolved item once (one queue row per item)."""
        ...

    async def get_entry(self, actor: ActorContext, item_id: UUID) -> MissingEntry | None:
        """Return None when the item is not assigned to this actor (foreign item indistinguishable)."""
        ...

    async def update_status(
        self, actor: ActorContext, item_id: UUID, status: str, staff_note: str, expected_revision: int
    ) -> MissingEntry: ...


async def record_missing(item_id: UUID, enquiry_id: UUID, *, repo: MissingPartsRepository) -> MissingEntry:
    """System-initiated: record an unresolved item once. Never fabricates stock or a catalogue row."""
    return await repo.record(item_id, enquiry_id)


async def update_missing_part(actor: ActorContext, request: F60Request, *, repo: MissingPartsRepository) -> F60Result:
    """Assigned staff move a missing item through its status with a note."""
    if request.status not in VALID_STATUSES:
        raise PartsIQError("VALIDATION_FAILED", internal_detail=f"status must be one of {sorted(VALID_STATUSES)}")
    if len(request.staff_note) > MAX_NOTE:
        raise PartsIQError("VALIDATION_FAILED", internal_detail="staff note too long")
    if request.status == "resolved" and not request.staff_note.strip():
        raise PartsIQError("VALIDATION_FAILED", internal_detail="resolving a missing part requires a staff explanation")
    entry = await repo.get_entry(actor, request.item_id)
    if entry is None:
        raise PartsIQError("NOT_FOUND", internal_detail="missing-part item not assigned to this actor")
    if entry.revision != request.expected_revision:
        raise PartsIQError("STALE_REVISION", internal_detail="a newer revision exists; reload the queue item")
    updated = await repo.update_status(
        actor, request.item_id, request.status, request.staff_note, request.expected_revision
    )
    return F60Result(id=updated.id, status=updated.status, updated_at=updated.updated_at)
