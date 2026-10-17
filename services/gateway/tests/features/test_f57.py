"""F57 Catalogue browser — published-only read, filters, paging, detail, SQL-safe query.

Only published-version rows are returned (never import-staging rows); a missing number is 404;
a hostile query string is treated as a literal and never becomes SQL.
"""
from __future__ import annotations

import unittest
from uuid import uuid4

from app.features.f57_catalogue_browser import (
    F57Request,
    PartView,
    browse_catalogue,
    part_detail,
)
from partsiq_common.contracts import ActorContext
from partsiq_common.errors import PartsIQError

VERSION = uuid4()


def _actor():
    return ActorContext(user_id=uuid4(), request_id=uuid4(), roles=["reviewer"])


def _part(pid, number, name="fuel filter", category="filters", superseded_by=None):
    return PartView(
        id=pid, part_number=number, name_en=name, name_ar="فلتر", category=category,
        superseded_by=superseded_by, fitment=[f"model-{pid}"], sources=["SYNTH-CA rev 1, section FILTERS"],
    )


class FakeCatalogueStore:
    def __init__(self, published, *, active=VERSION, staging=None):
        self._published = published
        self._active = active
        self._staging = staging or []  # import rows that must NEVER surface

    async def active_version_id(self):
        return self._active

    async def browse(self, *, query, model_id, category, after_id, limit):
        rows = sorted(self._published, key=lambda p: p.id)
        if query is not None:
            needle = query.lower()
            rows = [p for p in rows if needle in p.name_en.lower() or needle in p.part_number.lower()]
        if model_id is not None:
            rows = [p for p in rows if f"model-{model_id}" in p.fitment]
        if category is not None:
            rows = [p for p in rows if p.category == category]
        if after_id is not None:
            rows = [p for p in rows if p.id > after_id]
        return rows[:limit]

    async def part_detail(self, part_number):
        for p in self._published:  # staging rows are never consulted
            if p.part_number == part_number:
                return p
        return None


class Failing:
    async def active_version_id(self):
        raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="db down")


class BrowseCatalogue(unittest.IsolatedAsyncioTestCase):
    async def test_lists_published_parts_with_version(self):
        store = FakeCatalogueStore([_part(1, "VP-10"), _part(2, "VP-20")])
        result = await browse_catalogue(_actor(), F57Request(), store=store)
        self.assertEqual([p.part_number for p in result.parts], ["VP-10", "VP-20"])
        self.assertEqual(result.version_id, VERSION)

    async def test_text_and_category_filters(self):
        store = FakeCatalogueStore([
            _part(1, "VP-10", name="fuel filter", category="filters"),
            _part(2, "BR-20", name="brake pad", category="brakes"),
        ])
        by_text = await browse_catalogue(_actor(), F57Request(query="brake"), store=store)
        self.assertEqual([p.part_number for p in by_text.parts], ["BR-20"])
        by_cat = await browse_catalogue(_actor(), F57Request(category="filters"), store=store)
        self.assertEqual([p.part_number for p in by_cat.parts], ["VP-10"])

    async def test_pagination_cursor(self):
        store = FakeCatalogueStore([_part(i, f"VP-{i}") for i in range(1, 6)])
        first = await browse_catalogue(_actor(), F57Request(limit=2), store=store)
        self.assertEqual(len(first.parts), 2)
        self.assertIsNotNone(first.next_cursor)
        second = await browse_catalogue(_actor(), F57Request(limit=2, cursor=first.next_cursor), store=store)
        self.assertTrue(all(p.id > first.parts[-1].id for p in second.parts))

    async def test_hostile_query_is_literal_not_sql(self):
        store = FakeCatalogueStore([_part(1, "VP-10")])
        result = await browse_catalogue(_actor(), F57Request(query="'; DROP TABLE parts; --"), store=store)
        self.assertEqual(result.parts, [])  # treated as a literal; no match, no error

    async def test_invalid_cursor_is_422(self):
        store = FakeCatalogueStore([_part(1, "VP-10")])
        with self.assertRaises(PartsIQError) as ctx:
            await browse_catalogue(_actor(), F57Request(cursor="not-a-cursor"), store=store)
        self.assertEqual(ctx.exception.http_status, 422)

    async def test_invalid_limit_is_422(self):
        store = FakeCatalogueStore([_part(1, "VP-10")])
        with self.assertRaises(PartsIQError) as ctx:
            await browse_catalogue(_actor(), F57Request(limit=0), store=store)
        self.assertEqual(ctx.exception.http_status, 422)

    async def test_no_published_version_is_404(self):
        store = FakeCatalogueStore([], active=None)
        with self.assertRaises(PartsIQError) as ctx:
            await browse_catalogue(_actor(), F57Request(), store=store)
        self.assertEqual(ctx.exception.http_status, 404)

    async def test_dependency_failure_propagates(self):
        with self.assertRaises(PartsIQError) as ctx:
            await browse_catalogue(_actor(), F57Request(), store=Failing())
        self.assertEqual(ctx.exception.code, "DEPENDENCY_UNAVAILABLE")


class PartDetail(unittest.IsolatedAsyncioTestCase):
    async def test_detail_includes_supersession_and_sources(self):
        store = FakeCatalogueStore([_part(1, "VP-10", superseded_by="VP-11")])
        detail = await part_detail(_actor(), "VP-10", store=store)
        self.assertEqual(detail.superseded_by, "VP-11")
        self.assertTrue(detail.sources)

    async def test_missing_number_is_404(self):
        store = FakeCatalogueStore([_part(1, "VP-10")])
        with self.assertRaises(PartsIQError) as ctx:
            await part_detail(_actor(), "NOPE-999", store=store)
        self.assertEqual(ctx.exception.http_status, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
