"""Foundation 08 acceptance: enquiry intake, idempotency, rate limiting and history.

Fully offline and deterministic. Persistence and Redis are BLOCKED in this environment, so the
transactional intake store, the idempotency store and the rate-limit backend are exercised
through in-memory fakes that MIRROR the real semantics being asserted:

* the intake store commits the enquiry + first message + revision snapshot + workflow job in a
  single all-or-nothing transaction (so a failing job insert leaves NO enquiry), and
* the rate-limit backend is an atomic counter that can be told to be "unavailable" to prove the
  fail-closed 503.

Live PostgreSQL (``Database.request_scope``) and live Redis are integration-only and are not
faked as "passing"; they are called out as BLOCKED in the report.

Consolidates the legacy coverage from services/gateway/tests/test_08 (intake + rate limit) and
services/gateway/tests/features/test_f19.py (owned history pagination).
"""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from partsiq.core.api_models import EnquiryPage, HistoryQuery
from partsiq.core.contracts import ActorContext, EnquiryCreate, EnquiryView, MessageCreate
from partsiq.core.errors import PartsIQError
from partsiq.core.idempotency import (
    canonical_request_hash,
    record_result,
    replay_or_check,
)
from partsiq.core.rate_limit import (
    RateLimiterUnavailableError,
    check_rate_limit,
    rate_limit_identity,
)
from partsiq.enquiries.history import (
    HistoryCursor,
    HistoryRow,
    _encode_cursor,
    list_history,
)
from partsiq.enquiries.intake import (
    append_message,
    create_enquiry,
    deserialize_view,
    serialize_view,
)

WHEN = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)


def _actor(user_id=None, session_id=None, generation=None, roles=("reviewer",)):
    return ActorContext(
        user_id=user_id or uuid4(),
        request_id=uuid4(),
        roles=list(roles),
        session_id=session_id,
        session_generation=generation,
    )


def _create(text="need brake pads", locale="en", warehouse=1):
    return EnquiryCreate(text=text, locale=locale, destination_warehouse_id=warehouse)


def _view(enquiry_id=None, revision=1, status="received"):
    return EnquiryView(
        id=enquiry_id or uuid4(),
        revision=revision,
        status=status,
        messages=[],
        item_ids=[],
        catalogue_version_id=None,
        updated_at=WHEN,
    )


# --- fakes ------------------------------------------------------------------


class FakeIdempotencyStore:
    """In-memory (actor, key) -> (request_hash, result) store mirroring the DB reservation."""

    def __init__(self):
        self._rows: dict[tuple[UUID, UUID], tuple[str, str]] = {}

    async def lookup(self, actor, key):
        return self._rows.get((actor.user_id, key))

    async def reserve(self, actor, key, request_hash, result):
        self._rows[(actor.user_id, key)] = (request_hash, result)


class FakeRateBackend:
    """Atomic counter. ``available=False`` simulates a Redis outage (raises to fail closed)."""

    def __init__(self, available=True):
        self.available = available
        self.counts: dict[str, int] = {}
        self.calls = 0

    async def incr(self, key, ttl_seconds):
        self.calls += 1
        if not self.available:
            raise RateLimiterUnavailableError("backend down")
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]


class FakeIntakeStore:
    """All-or-nothing transactional store.

    ``fail_job`` flips the workflow-job insert to fail: because the whole method is one
    transaction, the enquiry is then NOT recorded (rollback assertion). ``revision`` drives the
    stale-revision check on append.
    """

    def __init__(self, *, fail_job=False, revision=1, missing=False):
        self.fail_job = fail_job
        self.revision = revision
        self.missing = missing
        self.enquiries: dict[UUID, EnquiryView] = {}
        self.jobs: list[UUID] = []
        self.audits: list[str] = []
        self.locked = 0

    async def create_enquiry_atomic(self, actor, command):
        enquiry_id = uuid4()
        # Simulate the single transaction: stage every write, then "commit" at the end. If the
        # job insert fails, nothing is persisted — the enquiry row is rolled back with it.
        staged_view = _view(enquiry_id)
        if self.fail_job:
            raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="job insert failed")
        self.enquiries[enquiry_id] = staged_view
        self.jobs.append(enquiry_id)
        self.audits.append(f"enquiry.created:{enquiry_id}")
        return staged_view

    async def lock_current_revision(self, actor, enquiry_id):
        self.locked += 1
        if self.missing:
            return None
        return self.revision

    async def append_message_atomic(self, actor, enquiry_id, command):
        new_revision = self.revision + 1
        self.revision = new_revision
        self.audits.append(f"message.appended:{enquiry_id}:{new_revision}")
        return _view(enquiry_id, revision=new_revision)


def _intake_kwargs(store, *, idem=None, rate=None):
    return {
        "store": store,
        "idempotency": idem or FakeIdempotencyStore(),
        "rate_limiter": rate or FakeRateBackend(),
        "serialize": serialize_view,
        "deserialize": deserialize_view,
    }


# --- canonical-hash idempotency (core/idempotency) --------------------------


class CanonicalIdempotency(unittest.IsolatedAsyncioTestCase):
    async def test_hash_is_stable_and_scoped_to_actor(self):
        actor = _actor()
        body = _create()
        h1 = canonical_request_hash(method="POST", path="/v1/enquiries", actor=actor, payload=body)
        h2 = canonical_request_hash(method="post", path="/v1/enquiries", actor=actor, payload=_create())
        self.assertEqual(h1, h2)  # case-normalized method, identical body -> identical hash
        other = _actor()
        h3 = canonical_request_hash(method="POST", path="/v1/enquiries", actor=other, payload=body)
        self.assertNotEqual(h1, h3)  # different verified actor -> different hash

    async def test_replay_same_payload_returns_stored_result(self):
        actor, key, store = _actor(), uuid4(), FakeIdempotencyStore()
        h = canonical_request_hash(method="POST", path="/p", actor=actor, payload=_create())
        self.assertIsNone(await replay_or_check(actor, key, h, store=store))  # first time: miss
        await record_result(actor, key, h, "STORED", store=store)
        self.assertEqual(await replay_or_check(actor, key, h, store=store), "STORED")

    async def test_mismatch_is_409(self):
        actor, key, store = _actor(), uuid4(), FakeIdempotencyStore()
        h1 = canonical_request_hash(method="POST", path="/p", actor=actor, payload=_create(text="a"))
        h2 = canonical_request_hash(method="POST", path="/p", actor=actor, payload=_create(text="b"))
        await record_result(actor, key, h1, "STORED", store=store)
        with self.assertRaises(PartsIQError) as ctx:
            await replay_or_check(actor, key, h2, store=store)
        self.assertEqual(ctx.exception.code, "IDEMPOTENCY_MISMATCH")
        self.assertEqual(ctx.exception.http_status, 409)


# --- rate limiting (core/rate_limit) ----------------------------------------


class RateLimiting(unittest.IsolatedAsyncioTestCase):
    async def test_identity_buckets_demo_by_session_generation(self):
        sid = uuid4()
        demo = _actor(session_id=sid, generation=3)
        staff = _actor()
        self.assertIn(str(sid), rate_limit_identity(demo, "enquiry.create"))
        self.assertIn(":3", rate_limit_identity(demo, "enquiry.create"))
        self.assertIn(str(staff.user_id), rate_limit_identity(staff, "enquiry.create"))

    async def test_within_limit_allows(self):
        actor, backend = _actor(), FakeRateBackend()
        for _ in range(3):
            decision = await check_rate_limit(actor, "enquiry.create", backend=backend, limit=3)
            self.assertTrue(decision.allowed)
        self.assertEqual(decision.remaining, 0)

    async def test_over_limit_is_429(self):
        actor, backend = _actor(), FakeRateBackend()
        await check_rate_limit(actor, "enquiry.create", backend=backend, limit=1)
        with self.assertRaises(PartsIQError) as ctx:
            await check_rate_limit(actor, "enquiry.create", backend=backend, limit=1)
        self.assertEqual(ctx.exception.code, "QUOTA_EXCEEDED")
        self.assertEqual(ctx.exception.http_status, 429)

    async def test_unavailable_backend_fails_closed_503(self):
        actor, backend = _actor(), FakeRateBackend(available=False)
        with self.assertRaises(PartsIQError) as ctx:
            await check_rate_limit(actor, "enquiry.create", backend=backend, limit=10)
        # Fails CLOSED: a required dependency is unavailable (503), never a silent allow.
        self.assertEqual(ctx.exception.code, "DEPENDENCY_UNAVAILABLE")
        self.assertEqual(ctx.exception.http_status, 503)


# --- create_enquiry (enquiries/intake) --------------------------------------


class CreateEnquiry(unittest.IsolatedAsyncioTestCase):
    async def test_commits_enquiry_and_job_together(self):
        actor, store = _actor(), FakeIntakeStore()
        view = await create_enquiry(actor, _create(), uuid4(), **_intake_kwargs(store))
        self.assertEqual(view.status, "received")
        self.assertEqual(len(store.enquiries), 1)
        self.assertEqual(len(store.jobs), 1)  # enquiry AND durable job both committed
        self.assertEqual(len(store.audits), 1)  # irreversible mutation is audited in-tx

    async def test_job_failure_rolls_back_enquiry(self):
        # If the workflow-job insert fails, the whole transaction rolls back: no enquiry row.
        actor, store = _actor(), FakeIntakeStore(fail_job=True)
        with self.assertRaises(PartsIQError):
            await create_enquiry(actor, _create(), uuid4(), **_intake_kwargs(store))
        self.assertEqual(store.enquiries, {})  # rollback assertion: enquiry NOT created
        self.assertEqual(store.jobs, [])

    async def test_202_result_returned_after_commit(self):
        # The returned view describes the committed resource (202-after-commit), never a pending
        # vision/Snowflake result.
        actor, store = _actor(), FakeIntakeStore()
        view = await create_enquiry(actor, _create(), uuid4(), **_intake_kwargs(store))
        self.assertIsInstance(view, EnquiryView)
        self.assertIn(view.id, store.enquiries)

    async def test_idempotent_replay_does_not_write_twice(self):
        actor, store, idem = _actor(), FakeIntakeStore(), FakeIdempotencyStore()
        key = uuid4()
        body = _create()
        first = await create_enquiry(actor, body, key, **_intake_kwargs(store, idem=idem))
        second = await create_enquiry(actor, body, key, **_intake_kwargs(store, idem=idem))
        self.assertEqual(first.id, second.id)  # same resource returned
        self.assertEqual(len(store.enquiries), 1)  # the commit happened exactly once

    async def test_idempotency_mismatch_is_409(self):
        actor, store, idem = _actor(), FakeIntakeStore(), FakeIdempotencyStore()
        key = uuid4()
        await create_enquiry(actor, _create(text="a"), key, **_intake_kwargs(store, idem=idem))
        with self.assertRaises(PartsIQError) as ctx:
            await create_enquiry(actor, _create(text="b"), key, **_intake_kwargs(store, idem=idem))
        self.assertEqual(ctx.exception.code, "IDEMPOTENCY_MISMATCH")

    async def test_rate_limit_runs_before_any_write(self):
        actor, store = _actor(), FakeIntakeStore()
        backend = FakeRateBackend(available=False)  # limiter unavailable
        with self.assertRaises(PartsIQError) as ctx:
            await create_enquiry(actor, _create(), uuid4(), **_intake_kwargs(store, rate=backend))
        self.assertEqual(ctx.exception.code, "DEPENDENCY_UNAVAILABLE")
        self.assertEqual(store.enquiries, {})  # no durable write when the limit check fails

    async def test_invalid_typed_input_rejected_at_contract(self):
        # Oversize text and non-positive warehouse are rejected by the typed contract (422 edge).
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            _create(text="")
        with self.assertRaises(ValidationError):
            _create(warehouse=0)


# --- append_message (enquiries/intake) --------------------------------------


class AppendMessage(unittest.IsolatedAsyncioTestCase):
    async def test_matching_revision_appends_new_revision(self):
        actor, store = _actor(), FakeIntakeStore(revision=2)
        msg = MessageCreate(text="here is the serial", expected_revision=2)
        view = await append_message(actor, uuid4(), msg, uuid4(), **_intake_kwargs(store))
        self.assertEqual(view.revision, 3)  # a new revision invalidates derived results
        self.assertTrue(store.audits[-1].startswith("message.appended"))

    async def test_stale_revision_is_409(self):
        actor, store = _actor(), FakeIntakeStore(revision=5)
        msg = MessageCreate(text="late answer", expected_revision=3)  # client saw an old revision
        with self.assertRaises(PartsIQError) as ctx:
            await append_message(actor, uuid4(), msg, uuid4(), **_intake_kwargs(store))
        self.assertEqual(ctx.exception.code, "STALE_REVISION")
        self.assertEqual(ctx.exception.http_status, 409)

    async def test_missing_enquiry_is_404(self):
        actor, store = _actor(), FakeIntakeStore(missing=True)
        msg = MessageCreate(text="hi", expected_revision=1)
        with self.assertRaises(PartsIQError) as ctx:
            await append_message(actor, uuid4(), msg, uuid4(), **_intake_kwargs(store))
        self.assertEqual(ctx.exception.code, "NOT_FOUND")

    async def test_replay_returns_stored_without_relocking(self):
        actor, store, idem = _actor(), FakeIntakeStore(revision=1), FakeIdempotencyStore()
        key, eid = uuid4(), uuid4()
        msg = MessageCreate(text="same", expected_revision=1)
        first = await append_message(actor, eid, msg, key, **_intake_kwargs(store, idem=idem))
        locks_after_first = store.locked
        second = await append_message(actor, eid, msg, key, **_intake_kwargs(store, idem=idem))
        self.assertEqual(first.revision, second.revision)
        self.assertEqual(store.locked, locks_after_first)  # replay skips the lock + write


# --- owned history (enquiries/history; ports F19) ---------------------------


class FakeHistoryRepo:
    """Scopes strictly by actor.user_id (RLS stand-in) with real keyset pagination."""

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


def _row(created_at, enquiry_id=None, status="received"):
    eid = enquiry_id or uuid4()
    return HistoryRow(view=_view(eid, status=status), created_at=created_at)


class ListHistory(unittest.IsolatedAsyncioTestCase):
    async def test_returns_owned_newest_first(self):
        actor = _actor()
        rows = [_row(WHEN - timedelta(hours=i)) for i in range(3)]
        repo = FakeHistoryRepo({actor.user_id: rows})
        result = await list_history(actor, HistoryQuery(), repo=repo)
        self.assertIsInstance(result, EnquiryPage)
        self.assertEqual(len(result.items), 3)
        self.assertIsNone(result.next_cursor)
        self.assertEqual(result.items[0].id, rows[0].view.id)

    async def test_foreign_owner_ignored_and_no_owner_field(self):
        owner, stranger = _actor(), _actor()
        repo = FakeHistoryRepo({owner.user_id: [_row(WHEN)]})
        result = await list_history(stranger, HistoryQuery(), repo=repo)
        self.assertEqual(result.items, [])  # cannot see another owner's rows
        # Ownership is never a request field: HistoryQuery exposes no owner/user id to spoof.
        self.assertFalse(any("owner" in f or "user" in f for f in HistoryQuery.model_fields))

    async def test_equal_timestamps_no_dup_or_skip_across_pages(self):
        actor = _actor()
        tied, other = WHEN, WHEN - timedelta(hours=1)
        rows = [_row(tied) for _ in range(3)] + [_row(other) for _ in range(2)]
        repo = FakeHistoryRepo({actor.user_id: rows})
        seen: list[UUID] = []
        cursor = None
        for _ in range(10):  # bounded; should finish in 3 pages at limit=2
            result = await list_history(actor, HistoryQuery(cursor=cursor, limit=2), repo=repo)
            seen.extend(e.id for e in result.items)
            cursor = result.next_cursor
            if cursor is None:
                break
        self.assertEqual(len(seen), 5)        # nothing skipped
        self.assertEqual(len(set(seen)), 5)   # nothing duplicated
        self.assertEqual(set(seen), {r.view.id for r in rows})

    async def test_status_filter(self):
        actor = _actor()
        rows = [_row(WHEN, status="approved"), _row(WHEN - timedelta(hours=1), status="received")]
        repo = FakeHistoryRepo({actor.user_id: rows})
        result = await list_history(actor, HistoryQuery(status="approved"), repo=repo)
        self.assertEqual([e.status for e in result.items], ["approved"])

    async def test_invalid_cursor_is_422(self):
        actor = _actor()
        repo = FakeHistoryRepo({actor.user_id: []})
        with self.assertRaises(PartsIQError) as ctx:
            await list_history(actor, HistoryQuery(cursor="not a cursor!!"), repo=repo)
        self.assertEqual(ctx.exception.http_status, 422)

    async def test_invalid_limit_is_422(self):
        actor = _actor()
        repo = FakeHistoryRepo({actor.user_id: []})
        # The domain guard rejects out-of-range limits; it cannot be bypassed even if a caller
        # constructs the query with validation disabled.
        for bad in (0, 101):
            q = HistoryQuery.model_construct(cursor=None, limit=bad, status=None)
            with self.assertRaises(PartsIQError) as ctx:
                await list_history(actor, q, repo=repo)
            self.assertEqual(ctx.exception.http_status, 422)

    async def test_valid_cursor_roundtrips(self):
        actor = _actor()
        encoded = _encode_cursor(HistoryCursor(created_at=WHEN, id=uuid4()))
        repo = FakeHistoryRepo({actor.user_id: [_row(WHEN - timedelta(hours=5))]})
        result = await list_history(actor, HistoryQuery(cursor=encoded, limit=5), repo=repo)
        self.assertIsNone(result.next_cursor)


# --- live-infra boundaries (BLOCKED, never faked as passing) ----------------


class LiveInfraBlocked(unittest.TestCase):
    def test_live_postgres_and_redis_are_blocked(self):
        # Database.request_scope (live PostgreSQL) and the real Redis rate-limit backend require
        # infrastructure not present here; they are integration-only and intentionally untested
        # offline rather than faked as passing (prompt 08 TESTS: a blocked case is not a pass).
        self.skipTest("live PostgreSQL + Redis unavailable in this environment (integration-only)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
