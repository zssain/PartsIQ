"""F57 Catalogue browser (owner: gateway; depends on 02, 06, 18, F59).

Read-only browse over the ACTIVE published catalogue version with model/category/free-text
filters and cursor pagination, plus a single-part detail with supersession, fitment and
sources. It only ever returns rows of the published version — never unpublished import-staging
rows (those live in a separate table the read store does not touch). A missing part number is a
404. The free-text query is always a bound parameter in the live adapter and a literal
substring match here, so a query string can never become SQL.

browse_catalogue/part_detail are pure over an injected CatalogueReadStore; the live read-replica
adapter (published-version-scoped, parameterized) is wired by the gateway owner and is BLOCKED.
"""
from __future__ import annotations

import base64
from typing import Protocol
from uuid import UUID

from partsiq_common.contracts import ActorContext, Contract
from partsiq_common.errors import PartsIQError

MAX_LIMIT = 100


class PartView(Contract):
    id: int
    part_number: str
    name_en: str
    name_ar: str
    category: str
    superseded_by: str | None = None
    fitment: list[str] = []
    sources: list[str] = []


class F57Request(Contract):
    query: str | None = None
    model_id: int | None = None
    category: str | None = None
    cursor: str | None = None
    limit: int = 20


class F57Result(Contract):
    parts: list[PartView]
    next_cursor: str | None
    version_id: UUID


class CatalogueReadStore(Protocol):
    async def active_version_id(self) -> UUID | None: ...

    async def browse(
        self, *, query: str | None, model_id: int | None, category: str | None, after_id: int | None, limit: int
    ) -> list[PartView]:
        """Published-version rows only, ordered by part id ascending, after ``after_id``."""
        ...

    async def part_detail(self, part_number: str) -> PartView | None:
        """A single published part (with fitment + sources), or None if unknown/unpublished."""
        ...


def _encode_cursor(part_id: int) -> str:
    return base64.urlsafe_b64encode(str(part_id).encode("ascii")).decode("ascii")


def _decode_cursor(value: str) -> int:
    try:
        return int(base64.urlsafe_b64decode(value.encode("ascii")).decode("ascii"))
    except (ValueError, TypeError) as exc:
        raise PartsIQError("VALIDATION_FAILED", internal_detail="cursor is not a valid pagination token") from exc


async def browse_catalogue(actor: ActorContext, request: F57Request, *, store: CatalogueReadStore) -> F57Result:
    """Browse the active published catalogue with filters + cursor paging."""
    if request.limit < 1 or request.limit > MAX_LIMIT:
        raise PartsIQError("VALIDATION_FAILED", internal_detail=f"limit must be between 1 and {MAX_LIMIT}")
    active = await store.active_version_id()
    if active is None:
        raise PartsIQError("NOT_FOUND", internal_detail="no published catalogue version")
    after_id = _decode_cursor(request.cursor) if request.cursor else None
    rows = await store.browse(
        query=request.query, model_id=request.model_id, category=request.category,
        after_id=after_id, limit=request.limit + 1,
    )
    has_more = len(rows) > request.limit
    page = rows[: request.limit]
    next_cursor = _encode_cursor(page[-1].id) if has_more and page else None
    return F57Result(parts=page, next_cursor=next_cursor, version_id=active)


async def part_detail(actor: ActorContext, part_number: str, *, store: CatalogueReadStore) -> PartView:
    """Return one published part with supersession/fitment/sources; unknown -> 404."""
    detail = await store.part_detail(part_number)
    if detail is None:
        raise PartsIQError("NOT_FOUND", internal_detail="part not found in the published catalogue")
    return detail
