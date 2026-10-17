"""F36 Staff inbox (owner: gateway; depends on 07, 20, F42, F43).

Lists the enquiries a staff member may act on — a reviewer sees only enquiries ASSIGNED to them
plus their own active demo enquiries; an admin sees all. Supports status / priority / overdue /
free-text filters and stable keyset pagination. The scoped_total count is computed within the
SAME access scope as the list, so a filtered count can never leak a global total.

Scoping and filtering are enforced by the injected (RLS-backed) repository; list_inbox owns the
cursor round-trip and limit validation. The live adapter is BLOCKED.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from partsiq_common.contracts import ActorContext, Contract, EnquiryView
from partsiq_common.errors import PartsIQError

MAX_LIMIT = 100


class F36Request(Contract):
    cursor: str | None = None
    limit: int = 20
    status: str | None = None
    priority: str | None = None
    overdue: bool = False
    query: str | None = None


class F36Result(Contract):
    enquiries: list[EnquiryView]
    next_cursor: str | None
    scoped_total: int


@dataclass(frozen=True, slots=True)
class InboxCursor:
    created_at: datetime
    id: UUID


@dataclass(frozen=True, slots=True)
class InboxRow:
    view: EnquiryView
    created_at: datetime


class InboxRepository(Protocol):
    async def list_scoped(
        self, actor: ActorContext, *, status: str | None, priority: str | None, overdue: bool,
        query: str | None, after: InboxCursor | None, limit: int,
    ) -> list[InboxRow]:
        """Rows within the actor's access scope, newest-first after the cursor."""
        ...

    async def scoped_count(
        self, actor: ActorContext, *, status: str | None, priority: str | None, overdue: bool, query: str | None
    ) -> int:
        """Count within the SAME access scope + filters (never a global total)."""
        ...


def _encode_cursor(cursor: InboxCursor) -> str:
    return base64.urlsafe_b64encode(f"{cursor.created_at.isoformat()}|{cursor.id}".encode()).decode("ascii")


def _decode_cursor(value: str) -> InboxCursor:
    try:
        timestamp, identifier = base64.urlsafe_b64decode(value.encode("ascii")).decode("utf-8").split("|", 1)
        return InboxCursor(created_at=datetime.fromisoformat(timestamp), id=UUID(identifier))
    except (ValueError, TypeError) as exc:
        raise PartsIQError("VALIDATION_FAILED", internal_detail="cursor is not a valid pagination token") from exc


async def list_inbox(actor: ActorContext, request: F36Request, *, repo: InboxRepository) -> F36Result:
    """List the staff inbox within the actor's access scope, with filters + stable paging."""
    if request.limit < 1 or request.limit > MAX_LIMIT:
        raise PartsIQError("VALIDATION_FAILED", internal_detail=f"limit must be between 1 and {MAX_LIMIT}")
    after = _decode_cursor(request.cursor) if request.cursor else None
    rows = await repo.list_scoped(
        actor, status=request.status, priority=request.priority, overdue=request.overdue,
        query=request.query, after=after, limit=request.limit + 1,
    )
    has_more = len(rows) > request.limit
    page = rows[: request.limit]
    next_cursor = (
        _encode_cursor(InboxCursor(created_at=page[-1].created_at, id=page[-1].view.id)) if has_more and page else None
    )
    scoped_total = await repo.scoped_count(
        actor, status=request.status, priority=request.priority, overdue=request.overdue, query=request.query
    )
    return F36Result(enquiries=[row.view for row in page], next_cursor=next_cursor, scoped_total=scoped_total)
