"""F43 Overdue indicators — UTC deadlines, overdue only for unresolved states.

Urgent items are due sooner than normal; an approved/rejected enquiry is never overdue; all
instants are tz-aware UTC so a display timezone cannot move the deadline; overdue sorts first.
"""
from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.features.f43_overdue_indicators import (
    DeadlineInput,
    F43Request,
    F43Result,
    classify_deadline,
    sort_overdue_first,
)
from partsiq_common.contracts import ActorContext
from partsiq_common.errors import PartsIQError

CREATED = datetime(2026, 10, 17, 0, 0, tzinfo=UTC)


def _actor():
    return ActorContext(user_id=uuid4(), request_id=uuid4(), roles=["reviewer"])


class FakeDeadlineStore:
    def __init__(self, data, *, raises=None):
        self._data = data
        self._raises = raises

    async def load_deadline_input(self, actor, enquiry_id):
        if self._raises is not None:
            raise self._raises
        return self._data


async def _classify(created=CREATED, urgency="normal", status="awaiting_review", now=None):
    store = FakeDeadlineStore(DeadlineInput(created_at=created, urgency=urgency, status=status))
    now = now or (CREATED + timedelta(hours=1))
    return await classify_deadline(_actor(), F43Request(enquiry_id=uuid4(), now=now), store=store)


class ClassifyDeadline(unittest.IsolatedAsyncioTestCase):
    async def test_normal_not_overdue_within_window(self):
        result = await _classify(urgency="normal", now=CREATED + timedelta(hours=1))
        self.assertFalse(result.overdue)
        self.assertEqual(result.due_at, CREATED + timedelta(hours=24))
        self.assertEqual(result.due_at.tzinfo, UTC)
        self.assertEqual(result.age_seconds, 3600)

    async def test_normal_overdue_past_window(self):
        result = await _classify(urgency="normal", now=CREATED + timedelta(hours=25))
        self.assertTrue(result.overdue)

    async def test_urgent_due_sooner(self):
        result = await _classify(urgency="urgent", now=CREATED + timedelta(hours=5))
        self.assertEqual(result.due_at, CREATED + timedelta(hours=4))
        self.assertTrue(result.overdue)

    async def test_approved_never_overdue(self):
        result = await _classify(status="approved", now=CREATED + timedelta(days=5))
        self.assertFalse(result.overdue)

    async def test_rejected_never_overdue(self):
        result = await _classify(status="rejected", now=CREATED + timedelta(days=5))
        self.assertFalse(result.overdue)

    async def test_deadline_is_utc_and_deterministic(self):
        # due_at is created_at + threshold in UTC, independent of any display timezone.
        a = await _classify(urgency="normal", now=CREATED + timedelta(hours=1))
        b = await _classify(urgency="normal", now=CREATED + timedelta(hours=2))
        self.assertEqual(a.due_at, b.due_at)  # the deadline does not shift with "now"

    async def test_age_never_negative(self):
        result = await _classify(now=CREATED - timedelta(hours=1))  # clock skew
        self.assertEqual(result.age_seconds, 0)

    async def test_missing_enquiry_not_found(self):
        store = FakeDeadlineStore(None)
        with self.assertRaises(PartsIQError) as ctx:
            await classify_deadline(_actor(), F43Request(enquiry_id=uuid4(), now=CREATED), store=store)
        self.assertEqual(ctx.exception.http_status, 404)

    async def test_dependency_failure_propagates(self):
        store = FakeDeadlineStore(None, raises=PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="down"))
        with self.assertRaises(PartsIQError) as ctx:
            await classify_deadline(_actor(), F43Request(enquiry_id=uuid4(), now=CREATED), store=store)
        self.assertEqual(ctx.exception.code, "DEPENDENCY_UNAVAILABLE")


class SortOverdueFirst(unittest.TestCase):
    def test_overdue_first_then_earliest_deadline(self):
        rows = [
            F43Result(due_at=CREATED + timedelta(hours=24), overdue=False, age_seconds=10),
            F43Result(due_at=CREATED + timedelta(hours=4), overdue=True, age_seconds=20),
            F43Result(due_at=CREATED + timedelta(hours=2), overdue=True, age_seconds=30),
        ]
        ordered = sort_overdue_first(rows)
        self.assertTrue(ordered[0].overdue and ordered[1].overdue)
        self.assertFalse(ordered[2].overdue)
        self.assertLess(ordered[0].due_at, ordered[1].due_at)  # earliest-due overdue first


if __name__ == "__main__":
    unittest.main(verbosity=2)
