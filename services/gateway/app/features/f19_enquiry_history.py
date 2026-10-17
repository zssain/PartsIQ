"""F19 Enquiry history (owner: gateway; depends on 07, 08, 19).

Returns the caller's OWN enquiry history, cursor-paginated and newest-first. Ownership is
derived from the verified ActorContext (user id for staff, session id + active generation for
a demo) — never from a client-supplied owner id, so a foreign owner id is structurally
ignored. A demo caller sees only the active generation (a reset bumps the generation and
hides prior rows). Pagination is keyset on the stable (created_at, id) pair, so equal
timestamps neither duplicate nor skip a record. An unpar'seable cursor is a 422.

list_history is pure over an injected HistoryRepository; the live Postgres adapter
(enquiries, RLS-scoped) is wired by the gateway owner and is BLOCKED here.
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


class F19Request(Contract):
    cursor: str | None = None
    limit: int = 20
    status: str | None = None


class F19Result(Contract):
    enquiries: list[EnquiryView]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class HistoryCursor:
    created_at: datetime
    id: UUID


@dataclass(frozen=True, slots=True)
class HistoryRow:
    """One history row: the list view plus the created_at the cursor orders on."""

    view: EnquiryView
    created_at: datetime


class HistoryRepository(Protocol):
    async def list_owned(
        self, actor: ActorContext, *, status: str | None, after: HistoryCursor | None, limit: int
    ) -> list[HistoryRow]:
        """Return up to ``limit`` OWN rows in (created_at DESC, id DESC) order strictly after ``after``."""
        ...


def _encode_cursor(cursor: HistoryCursor) -> str:
    raw = f"{cursor.created_at.isoformat()}|{cursor.id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def _decode_cursor(value: str) -> HistoryCursor:
    try:
        raw = base64.urlsafe_b64decode(value.encode("ascii")).decode("utf-8")
        timestamp, identifier = raw.split("|", 1)
        return HistoryCursor(created_at=datetime.fromisoformat(timestamp), id=UUID(identifier))
    except (ValueError, TypeError) as exc:
        raise PartsIQError("VALIDATION_FAILED", internal_detail="cursor is not a valid pagination token") from exc


async def list_history(actor: ActorContext, request: F19Request, *, repo: HistoryRepository) -> F19Result:
    """List the caller's own enquiries, newest-first, with a next_cursor when more remain."""
    if request.limit < 1 or request.limit > MAX_LIMIT:
        raise PartsIQError("VALIDATION_FAILED", internal_detail=f"limit must be between 1 and {MAX_LIMIT}")
    after = _decode_cursor(request.cursor) if request.cursor else None
    # Over-fetch by one to learn whether a further page exists without a second round-trip.
    rows = await repo.list_owned(actor, status=request.status, after=after, limit=request.limit + 1)
    has_more = len(rows) > request.limit
    page = rows[: request.limit]
    next_cursor = (
        _encode_cursor(HistoryCursor(created_at=page[-1].created_at, id=page[-1].view.id))
        if has_more and page
        else None
    )
    return F19Result(enquiries=[row.view for row in page], next_cursor=next_cursor)
