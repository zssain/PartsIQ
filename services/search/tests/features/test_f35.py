"""F35 Stock freshness — freshness window, re-read, future/stale/changed flagging.

A future timestamp is flagged; a snapshot older than the window is not fresh; a current
available below the allocated quantity (allocation no longer possible) is flagged; a refreshed
snapshot forces re-planning. Stale stock is surfaced as not-fresh, never a guarantee.
"""
from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.features.f35_stock_freshness import (
    CurrentStock,
    F35Request,
    check_stock_freshness,
)
from partsiq_common.contracts import ActorContext, Allocation, VerifiedFacts, VerifiedItem
from partsiq_common.errors import PartsIQError

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _actor():
    return ActorContext(user_id=uuid4(), request_id=uuid4(), roles=["reviewer"])


def _facts(stamp, *, qty="2", warehouse=1, part=10, item_id=None):
    item_id = item_id or uuid4()
    return VerifiedFacts(
        enquiry_id=uuid4(), revision=1, catalogue_version_id=uuid4(),
        items=[VerifiedItem(
            item_id=item_id, configuration_id=100, part_id=part, part_number="VP-10",
            name_en="fuel filter", name_ar="فلتر", requested_quantity=Decimal(qty),
            allocations=[Allocation(warehouse_id=warehouse, quantity=Decimal(qty), transfer_days=2, stock_updated_at=stamp)],
            shortage=Decimal("0"), source_reference="SYNTH-CA rev 1, section FILTERS", evidence_id=uuid4(),
        )],
    )


class FakeReader:
    def __init__(self, available="5", updated_at=NOW):
        self._available = Decimal(available)
        self._updated_at = updated_at

    async def current_stock(self, part_id, warehouse_id):
        return CurrentStock(available=self._available, updated_at=self._updated_at)


class MissingReader:
    async def current_stock(self, part_id, warehouse_id):
        return None


class Failing:
    async def current_stock(self, part_id, warehouse_id):
        raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="stock down")


class CheckStockFreshness(unittest.IsolatedAsyncioTestCase):
    async def test_fresh_when_recent_and_sufficient(self):
        facts = _facts(NOW - timedelta(minutes=1))
        reader = FakeReader(available="5", updated_at=NOW - timedelta(minutes=1))
        result = await check_stock_freshness(_actor(), F35Request(facts=facts, max_age_seconds=3600), reader=reader, now=NOW)
        self.assertTrue(result.fresh)
        self.assertEqual(result.changed_item_ids, [])
        self.assertEqual(result.checked_at, NOW)

    async def test_stale_timestamp_not_fresh(self):
        item = uuid4()
        facts = _facts(NOW - timedelta(hours=5), item_id=item)
        result = await check_stock_freshness(
            _actor(), F35Request(facts=facts, max_age_seconds=3600), reader=FakeReader(updated_at=NOW - timedelta(hours=5)), now=NOW
        )
        self.assertFalse(result.fresh)
        self.assertIn(item, result.changed_item_ids)

    async def test_future_timestamp_flagged(self):
        item = uuid4()
        facts = _facts(NOW + timedelta(hours=1), item_id=item)
        result = await check_stock_freshness(
            _actor(), F35Request(facts=facts, max_age_seconds=3600), reader=FakeReader(), now=NOW
        )
        self.assertFalse(result.fresh)
        self.assertIn(item, result.changed_item_ids)

    async def test_changed_stock_no_longer_sufficient(self):
        item = uuid4()
        facts = _facts(NOW - timedelta(minutes=1), qty="4", item_id=item)
        reader = FakeReader(available="1", updated_at=NOW - timedelta(minutes=1))  # only 1 left now
        result = await check_stock_freshness(
            _actor(), F35Request(facts=facts, max_age_seconds=3600), reader=reader, now=NOW
        )
        self.assertFalse(result.fresh)
        self.assertIn(item, result.changed_item_ids)

    async def test_refreshed_snapshot_forces_replan(self):
        item = uuid4()
        facts = _facts(NOW - timedelta(minutes=5), item_id=item)
        reader = FakeReader(available="5", updated_at=NOW - timedelta(minutes=1))  # refreshed since planning
        result = await check_stock_freshness(
            _actor(), F35Request(facts=facts, max_age_seconds=3600), reader=reader, now=NOW
        )
        self.assertIn(item, result.changed_item_ids)

    async def test_unknown_current_stock_flagged(self):
        item = uuid4()
        facts = _facts(NOW - timedelta(minutes=1), item_id=item)
        result = await check_stock_freshness(
            _actor(), F35Request(facts=facts, max_age_seconds=3600), reader=MissingReader(), now=NOW
        )
        self.assertIn(item, result.changed_item_ids)

    async def test_nonpositive_max_age_rejected(self):
        with self.assertRaises(PartsIQError) as ctx:
            await check_stock_freshness(
                _actor(), F35Request(facts=_facts(NOW), max_age_seconds=0), reader=FakeReader(), now=NOW
            )
        self.assertEqual(ctx.exception.http_status, 422)

    async def test_dependency_failure_propagates(self):
        facts = _facts(NOW - timedelta(minutes=1))
        with self.assertRaises(PartsIQError) as ctx:
            await check_stock_freshness(
                _actor(), F35Request(facts=facts, max_age_seconds=3600), reader=Failing(), now=NOW
            )
        self.assertEqual(ctx.exception.code, "DEPENDENCY_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
