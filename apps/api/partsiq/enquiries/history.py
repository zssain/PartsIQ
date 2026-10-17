"""Owned enquiry history (foundation 08; ports feature F19).

Consolidated from ``services/gateway/app/features/f19_enquiry_history.py`` and adapted to the
kit contracts (:class:`HistoryQuery` in, :class:`EnquiryPage` out). Returns the caller's OWN
enquiry history, newest-first, keyset-paginated. Ownership is derived from the verified
:class:`ActorContext` (``user_id`` for staff/customer; ``session_id`` + active
``session_generation`` for a demo caller) — NEVER from a client-supplied owner id, so a foreign
owner id is structurally impossible to request. A demo reset bumps the generation and hides the
prior rows.

Pagination is keyset over the stable ``(created_at, id)`` pair so equal timestamps neither
duplicate nor skip a record; the cursor is an opaque base64 token whose contents are not part
of the public contract. An unparseable cursor is a 422; ``limit`` must be 1..100 (a value
outside that range is a 422 even though the typed model also guards it at the edge).

``list_history`` is pure over an injected :class:`HistoryRepository`; the live RLS-scoped
asyncpg adapter (``enquiries`` filtered to the owner) is wired by the API owner and is BLOCKED
here.
"""
from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from partsiq.core.api_models import EnquiryPage, HistoryQuery
from partsiq.core.contracts import ActorContext, EnquiryView
from partsiq.core.errors import PartsIQError

MIN_LIMIT = 1
MAX_LIMIT = 100


@dataclass(frozen=True, slots=True)
class HistoryCursor:
    """The keyset position: the ``(created_at, id)`` of the last row returned."""

    created_at: datetime
    id: UUID


@dataclass(frozen=True, slots=True)
class HistoryRow:
    """One history row: the list view plus the ``created_at`` the cursor orders on."""

    view: EnquiryView
    created_at: datetime


@runtime_checkable
class HistoryRepository(Protocol):
    async def list_owned(
        self,
        actor: ActorContext,
        *,
        status: str | None,
        after: HistoryCursor | None,
        limit: int,
    ) -> list[HistoryRow]:
        """Return up to ``limit`` OWN rows in ``(created_at DESC, id DESC)`` order strictly
        after ``after``. Ownership is enforced from ``actor`` (RLS), never a request field."""
        ...


def _encode_cursor(cursor: HistoryCursor) -> str:
    raw = f"{cursor.created_at.isoformat()}|{cursor.id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def _decode_cursor(value: str) -> HistoryCursor:
    try:
        raw = base64.urlsafe_b64decode(value.encode("ascii")).decode("utf-8")
        timestamp, identifier = raw.split("|", 1)
        return HistoryCursor(
            created_at=datetime.fromisoformat(timestamp), id=UUID(identifier)
        )
    except (ValueError, TypeError, binascii.Error, UnicodeDecodeError) as exc:
        raise PartsIQError(
            "VALIDATION_FAILED",
            internal_detail="cursor is not a valid pagination token",
        ) from exc


async def list_history(
    actor: ActorContext, query: HistoryQuery, *, repo: HistoryRepository
) -> EnquiryPage:
    """List the caller's own enquiries, newest-first, with a ``next_cursor`` when more remain.

    The limit is validated to 1..100 and the cursor is decoded (invalid -> 422) before any
    repository call. The repository over-fetches by one to detect a further page without a
    second round-trip; the ``next_cursor`` is built from the last returned row's stable key.
    """
    if query.limit < MIN_LIMIT or query.limit > MAX_LIMIT:
        raise PartsIQError(
            "VALIDATION_FAILED",
            internal_detail=f"limit must be between {MIN_LIMIT} and {MAX_LIMIT}",
        )
    after = _decode_cursor(query.cursor) if query.cursor else None
    rows = await repo.list_owned(
        actor, status=query.status, after=after, limit=query.limit + 1
    )
    has_more = len(rows) > query.limit
    page = rows[: query.limit]
    next_cursor = (
        _encode_cursor(HistoryCursor(created_at=page[-1].created_at, id=page[-1].view.id))
        if has_more and page
        else None
    )
    return EnquiryPage(items=[row.view for row in page], next_cursor=next_cursor)
