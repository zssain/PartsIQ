"""F60 Missing-parts queue — record once, assigned-staff status updates with notes.

Resolving requires an explanation; a foreign item is denied (404); a stale revision is 409;
the queue stores no fabricated stock; status updates never create catalogue rows.
"""
from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from app.features.f60_missing_parts_queue import (
    F60Request,
    MissingEntry,
    record_missing,
    update_missing_part,
)
from partsiq_common.contracts import ActorContext
from partsiq_common.errors import PartsIQError

WHEN = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _actor(user_id=None):
    return ActorContext(user_id=user_id or uuid4(), request_id=uuid4(), roles=["reviewer"])


class FakeMissingRepo:
    def __init__(self, assigned_to):
        self._assigned_to = assigned_to
        self._by_item: dict = {}

    async def record(self, item_id, enquiry_id):
        if item_id not in self._by_item:
            self._by_item[item_id] = MissingEntry(
                id=uuid4(), item_id=item_id, enquiry_id=enquiry_id, assigned_to=self._assigned_to,
                status="open", staff_note="", revision=1, updated_at=WHEN,
            )
        return self._by_item[item_id]

    async def get_entry(self, actor, item_id):
        entry = self._by_item.get(item_id)
        if entry is None or entry.assigned_to != actor.user_id:
            return None
        return entry

    async def update_status(self, actor, item_id, status, staff_note, expected_revision):
        entry = self._by_item[item_id]
        updated = replace(entry, status=status, staff_note=staff_note, revision=entry.revision + 1, updated_at=WHEN)
        self._by_item[item_id] = updated
        return updated


class Failing:
    async def get_entry(self, *a, **k):
        raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="db down")


class RecordMissing(unittest.IsolatedAsyncioTestCase):
    async def test_record_once_is_idempotent_and_has_no_stock(self):
        repo = FakeMissingRepo(assigned_to=uuid4())
        item, enquiry = uuid4(), uuid4()
        a = await record_missing(item, enquiry, repo=repo)
        b = await record_missing(item, enquiry, repo=repo)
        self.assertEqual(a.id, b.id)  # recorded once
        self.assertFalse(hasattr(a, "available"))  # empty result, never fabricated stock
        self.assertEqual(a.enquiry_id, enquiry)  # links back to the enquiry


class UpdateMissingPart(unittest.IsolatedAsyncioTestCase):
    async def _setup(self):
        staff = _actor()
        repo = FakeMissingRepo(assigned_to=staff.user_id)
        item = uuid4()
        await repo.record(item, uuid4())
        return staff, repo, item

    async def test_investigating_update(self):
        staff, repo, item = await self._setup()
        result = await update_missing_part(
            staff, F60Request(item_id=item, status="investigating", staff_note="checking supplier", expected_revision=1),
            repo=repo,
        )
        self.assertEqual(result.status, "investigating")

    async def test_resolved_requires_explanation(self):
        staff, repo, item = await self._setup()
        with self.assertRaises(PartsIQError) as ctx:
            await update_missing_part(
                staff, F60Request(item_id=item, status="resolved", staff_note="   ", expected_revision=1), repo=repo
            )
        self.assertEqual(ctx.exception.http_status, 422)

    async def test_resolved_with_explanation_ok(self):
        staff, repo, item = await self._setup()
        result = await update_missing_part(
            staff, F60Request(item_id=item, status="resolved", staff_note="added to next import", expected_revision=1),
            repo=repo,
        )
        self.assertEqual(result.status, "resolved")

    async def test_invalid_status_rejected(self):
        staff, repo, item = await self._setup()
        with self.assertRaises(PartsIQError) as ctx:
            await update_missing_part(
                staff, F60Request(item_id=item, status="in_stock", staff_note="x", expected_revision=1), repo=repo
            )
        self.assertEqual(ctx.exception.http_status, 422)

    async def test_foreign_item_denied(self):
        _staff, repo, item = await self._setup()
        stranger = _actor()
        with self.assertRaises(PartsIQError) as ctx:
            await update_missing_part(
                stranger, F60Request(item_id=item, status="investigating", staff_note="x", expected_revision=1),
                repo=repo,
            )
        self.assertEqual(ctx.exception.http_status, 404)

    async def test_stale_revision_rejected(self):
        staff, repo, item = await self._setup()
        with self.assertRaises(PartsIQError) as ctx:
            await update_missing_part(
                staff, F60Request(item_id=item, status="investigating", staff_note="x", expected_revision=99),
                repo=repo,
            )
        self.assertEqual(ctx.exception.http_status, 409)

    async def test_dependency_failure_propagates(self):
        with self.assertRaises(PartsIQError) as ctx:
            await update_missing_part(
                _actor(), F60Request(item_id=uuid4(), status="investigating", staff_note="x", expected_revision=1),
                repo=Failing(),
            )
        self.assertEqual(ctx.exception.code, "DEPENDENCY_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
