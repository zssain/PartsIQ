"""F19 Enquiry history — owned, cursor-paginated, stable (created_at, id) ordering.

Ownership comes from the ActorContext, so a foreign owner id is structurally impossible to
request. Keyset pagination over (created_at, id) means equal timestamps neither duplicate nor
skip a record; an unparseable cursor is a 422; a bad limit is a 422.
"""
from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.features.f19_enquiry_history import (
    F19Request,
    HistoryCursor,
    HistoryRow,
    _encode_cursor,
    list_history,
)
from partsiq_common.contracts import ActorContext, EnquiryView
from partsiq_common.errors import PartsIQError

WHEN = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _actor(user_id=None):
    return ActorContext(user_id=user_id or uuid4(), request_id=uuid4(), roles=["reviewer"])


def _view(enquiry_id=None, status="received"):
    return EnquiryView(
        id=enquiry_id or uuid4(), revision=1, status=status, messages=[], item_ids=[],
        catalogue_version_id=None, updated_at=WHEN,
    )


def _row(created_at, enquiry_id=None, status="received"):
    eid = enquiry_id or uuid4()
    return HistoryRow(view=_view(eid, status), created_at=created_at)


class FakeHistoryRepo:
    """Scopes strictly by actor.user_id (RLS stand-in) and implements real keyset pagination."""

    def __init__(self, rows_by_owner):
        self._rows_by_owner = rows_by_owner

    async def list_owned(self, actor, *, status, after, limit):
        rows = list(self._rows_by_owner.get(actor.user_id, []))
        if status is not None:
            rows = [r for r in rows if r.view.status == status]
        rows.sort(key=lambda r: (r.created_at, r.view.id), reverse=True)  # newest-first, stable
        if after is not None:
            rows = [r for r in rows if (r.created_at, r.view.id) < (after.created_at, after.id)]
        return rows[:limit]


class Failing:
    async def list_owned(self, *a, **k):
        raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="db down")


class ListHistory(unittest.IsolatedAsyncioTestCase):
    async def test_returns_owned_history_newest_first(self):
        actor = _actor()
        rows = [_row(WHEN - timedelta(hours=i)) for i in range(3)]
        repo = FakeHistoryRepo({actor.user_id: rows})
        result = await list_history(actor, F19Request(), repo=repo)
        self.assertEqual(len(result.enquiries), 3)
        self.assertIsNone(result.next_cursor)
        self.assertEqual(result.enquiries[0].id, rows[0].view.id)  # newest first

    async def test_foreign_owner_ignored(self):
        owner, stranger = _actor(), _actor()
        repo = FakeHistoryRepo({owner.user_id: [_row(WHEN)]})
        result = await list_history(stranger, F19Request(), repo=repo)  # a different actor
        self.assertEqual(result.enquiries, [])  # cannot see the owner's rows; no owner field to spoof
        self.assertFalse(any(f == "owner" or "owner" in f for f in F19Request.model_fields))

    async def test_pagination_with_equal_timestamps_no_dup_or_skip(self):
        actor = _actor()
        # Five rows: three share one timestamp, two share another -> ties disambiguated by id.
        tied = WHEN
        other = WHEN - timedelta(hours=1)
        rows = [_row(tied) for _ in range(3)] + [_row(other) for _ in range(2)]
        repo = FakeHistoryRepo({actor.user_id: rows})

        seen: list[UUID] = []
        cursor = None
        for _ in range(10):  # bounded loop; should terminate in 3 pages at limit=2
            result = await list_history(actor, F19Request(cursor=cursor, limit=2), repo=repo)
            seen.extend(e.id for e in result.enquiries)
            cursor = result.next_cursor
            if cursor is None:
                break
        self.assertEqual(len(seen), 5)             # nothing skipped
        self.assertEqual(len(set(seen)), 5)        # nothing duplicated
        self.assertEqual(set(seen), {r.view.id for r in rows})

    async def test_status_filter(self):
        actor = _actor()
        rows = [_row(WHEN, status="approved"), _row(WHEN - timedelta(hours=1), status="received")]
        repo = FakeHistoryRepo({actor.user_id: rows})
        result = await list_history(actor, F19Request(status="approved"), repo=repo)
        self.assertEqual([e.status for e in result.enquiries], ["approved"])

    async def test_invalid_cursor_is_422(self):
        actor = _actor()
        repo = FakeHistoryRepo({actor.user_id: []})
        with self.assertRaises(PartsIQError) as ctx:
            await list_history(actor, F19Request(cursor="not-a-cursor!!"), repo=repo)
        self.assertEqual(ctx.exception.http_status, 422)

    async def test_invalid_limit_is_422(self):
        actor = _actor()
        repo = FakeHistoryRepo({actor.user_id: []})
        for bad in (0, 101):
            with self.assertRaises(PartsIQError) as ctx:
                await list_history(actor, F19Request(limit=bad), repo=repo)
            self.assertEqual(ctx.exception.http_status, 422)

    async def test_cursor_roundtrip_is_opaque_and_stable(self):
        cursor = HistoryCursor(created_at=WHEN, id=uuid4())
        encoded = _encode_cursor(cursor)
        # A valid encoded cursor must decode without error via a real paginated call.
        actor = _actor()
        repo = FakeHistoryRepo({actor.user_id: [_row(WHEN - timedelta(hours=5))]})
        result = await list_history(actor, F19Request(cursor=encoded, limit=5), repo=repo)
        self.assertIsNone(result.next_cursor)

    async def test_dependency_failure_propagates(self):
        with self.assertRaises(PartsIQError) as ctx:
            await list_history(_actor(), F19Request(), repo=Failing())
        self.assertEqual(ctx.exception.code, "DEPENDENCY_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
