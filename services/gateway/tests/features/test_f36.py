"""F36 Staff inbox — access-scoped listing + counts, filters, stable keyset pagination.

A reviewer sees only assigned enquiries; an admin sees all; unassigned real enquiries are hidden
from a reviewer; scoped_total stays within the access scope (never a global count); filters and
paging behave; bad limit/cursor are 422.
"""
from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.features.f36_staff_inbox import F36Request, InboxRow, list_inbox
from partsiq_common.contracts import ActorContext, EnquiryView
from partsiq_common.errors import PartsIQError

BASE = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _admin():
    return ActorContext(user_id=uuid4(), request_id=uuid4(), roles=["admin"])


def _reviewer(user_id=None):
    return ActorContext(user_id=user_id or uuid4(), request_id=uuid4(), roles=["reviewer"])


@dataclass
class Row:
    id: UUID
    created_at: datetime
    assigned_to: UUID | None
    status: str
    priority: str
    overdue: bool
    text: str


def _view(row: Row) -> EnquiryView:
    return EnquiryView(id=row.id, revision=1, status=row.status, messages=[], item_ids=[],
                       catalogue_version_id=None, updated_at=row.created_at)


class FakeInboxRepo:
    def __init__(self, rows, *, raises=None):
        self._rows = rows
        self._raises = raises

    def _scoped(self, actor):
        if "admin" in actor.roles:
            return list(self._rows)
        return [r for r in self._rows if r.assigned_to == actor.user_id]  # reviewer: assigned only

    def _filtered(self, actor, status, priority, overdue, query):
        rows = self._scoped(actor)
        if status is not None:
            rows = [r for r in rows if r.status == status]
        if priority is not None:
            rows = [r for r in rows if r.priority == priority]
        if overdue:
            rows = [r for r in rows if r.overdue]
        if query is not None:
            rows = [r for r in rows if query.lower() in r.text.lower()]
        return rows

    async def list_scoped(self, actor, *, status, priority, overdue, query, after, limit):
        if self._raises is not None:
            raise self._raises
        rows = sorted(self._filtered(actor, status, priority, overdue, query),
                      key=lambda r: (r.created_at, str(r.id)), reverse=True)
        if after is not None:
            rows = [r for r in rows if (r.created_at, str(r.id)) < (after.created_at, str(after.id))]
        return [InboxRow(view=_view(r), created_at=r.created_at) for r in rows[:limit]]

    async def scoped_count(self, actor, *, status, priority, overdue, query):
        return len(self._filtered(actor, status, priority, overdue, query))


def _rows(reviewer_id):
    return [
        Row(uuid4(), BASE - timedelta(hours=1), reviewer_id, "awaiting_review", "urgent", True, "fuel filter"),
        Row(uuid4(), BASE - timedelta(hours=2), reviewer_id, "processing", "normal", False, "brake pad"),
        Row(uuid4(), BASE - timedelta(hours=3), uuid4(), "awaiting_review", "urgent", True, "hidden"),  # someone else
    ]


class ListInbox(unittest.IsolatedAsyncioTestCase):
    async def test_reviewer_sees_only_assigned(self):
        reviewer = _reviewer()
        repo = FakeInboxRepo(_rows(reviewer.user_id))
        result = await list_inbox(reviewer, F36Request(), repo=repo)
        self.assertEqual(len(result.enquiries), 2)         # the two assigned to them
        self.assertEqual(result.scoped_total, 2)           # scoped, not the global 3

    async def test_admin_sees_all(self):
        rows = _rows(uuid4())
        result = await list_inbox(_admin(), F36Request(), repo=FakeInboxRepo(rows))
        self.assertEqual(result.scoped_total, 3)

    async def test_unassigned_hidden_from_reviewer(self):
        reviewer = _reviewer()
        rows = _rows(reviewer.user_id)
        hidden_id = rows[2].id
        result = await list_inbox(reviewer, F36Request(), repo=FakeInboxRepo(rows))
        self.assertNotIn(hidden_id, [e.id for e in result.enquiries])

    async def test_status_filter(self):
        reviewer = _reviewer()
        repo = FakeInboxRepo(_rows(reviewer.user_id))
        result = await list_inbox(reviewer, F36Request(status="processing"), repo=repo)
        self.assertEqual([e.status for e in result.enquiries], ["processing"])
        self.assertEqual(result.scoped_total, 1)

    async def test_overdue_and_query_filters(self):
        reviewer = _reviewer()
        repo = FakeInboxRepo(_rows(reviewer.user_id))
        overdue = await list_inbox(reviewer, F36Request(overdue=True), repo=repo)
        self.assertTrue(all(e.status == "awaiting_review" for e in overdue.enquiries))
        text = await list_inbox(reviewer, F36Request(query="brake"), repo=repo)
        self.assertEqual(text.scoped_total, 1)

    async def test_pagination_stable_and_total_scope_constant(self):
        reviewer = _reviewer()
        rows = _rows(reviewer.user_id) + [
            Row(uuid4(), BASE - timedelta(hours=4), reviewer.user_id, "processing", "normal", False, "clutch"),
        ]
        repo = FakeInboxRepo(rows)
        seen, cursor = [], None
        for _ in range(10):
            page = await list_inbox(reviewer, F36Request(limit=1, cursor=cursor), repo=repo)
            seen.extend(e.id for e in page.enquiries)
            self.assertEqual(page.scoped_total, 3)  # scope count constant across pages
            cursor = page.next_cursor
            if cursor is None:
                break
        self.assertEqual(len(seen), len(set(seen)))  # no duplicates
        self.assertEqual(len(seen), 3)               # no skips

    async def test_invalid_limit_is_422(self):
        reviewer = _reviewer()
        with self.assertRaises(PartsIQError) as ctx:
            await list_inbox(reviewer, F36Request(limit=0), repo=FakeInboxRepo(_rows(reviewer.user_id)))
        self.assertEqual(ctx.exception.http_status, 422)

    async def test_invalid_cursor_is_422(self):
        reviewer = _reviewer()
        with self.assertRaises(PartsIQError) as ctx:
            await list_inbox(reviewer, F36Request(cursor="nope"), repo=FakeInboxRepo(_rows(reviewer.user_id)))
        self.assertEqual(ctx.exception.http_status, 422)

    async def test_dependency_failure_propagates(self):
        repo = FakeInboxRepo([], raises=PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="down"))
        with self.assertRaises(PartsIQError) as ctx:
            await list_inbox(_reviewer(), F36Request(), repo=repo)
        self.assertEqual(ctx.exception.code, "DEPENDENCY_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
