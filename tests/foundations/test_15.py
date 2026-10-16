"""Acceptance tests for prompt 15 — worker leases and sweeper (foundation gate).

Offline: fake job store + queue stand in for Postgres (FOR UPDATE SKIP LOCKED) and Redis.
The lease lifecycle (fresh token on claim, renew-while-ours, token+revision+generation
fencing on finish), persist-before-dispatch with dedupe, bounded per-kind concurrency,
graceful-shutdown claim gating, and sweeper reclaim with max-attempts are all exercised
without infrastructure. The live asyncpg/Redis adapters are BLOCKED. Covers F05, F14,
F51, F52.
"""
from __future__ import annotations

import sys
import unittest
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "partsiq_common"))
sys.path.insert(0, str(REPO_ROOT / "services" / "worker"))

from app.dispatcher import ConcurrencyGuard, Dispatcher, enqueue_job  # noqa: E402
from app.leases import LEASE_SECONDS, claim_job, finish_job, heartbeat  # noqa: E402
from app.sweeper import sweep_once  # noqa: E402
from partsiq_common.contracts import JobLease, JobResult  # noqa: E402

WHEN = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


@dataclass
class Row:
    id: UUID
    kind: str
    status: str = "pending"
    attempts: int = 0
    max_attempts: int = 3
    lease_token: UUID | None = None
    lease_expires_at: datetime | None = None
    available_at: datetime = WHEN
    enquiry_id: UUID | None = None
    revision: int | None = None
    session_generation: int | None = None
    dedupe_key: str = ""
    payload: dict = field(default_factory=dict)
    result: JobResult | None = None


class FakeJobStore:
    def __init__(self, rows=None, *, locked=None, fence=None):
        self.rows: dict[UUID, Row] = {r.id: r for r in (rows or [])}
        self.locked: set[UUID] = set(locked or ())
        self.fence = fence  # (revision, generation) or None
        self.by_dedupe: dict[str, UUID] = {r.dedupe_key: r.id for r in self.rows.values() if r.dedupe_key}

    async def claim(self, *, job_id, worker_id, token, lease_seconds):
        row = self.rows.get(job_id)
        if row is None or job_id in self.locked:        # SKIP LOCKED: someone else holds it
            return None
        claimable = row.status == "pending" or (
            row.status == "running" and row.lease_expires_at is not None and row.lease_expires_at <= WHEN
        )
        if not claimable:
            return None
        row.status = "running"
        row.lease_token = token
        row.attempts += 1
        row.lease_expires_at = WHEN + timedelta(seconds=lease_seconds)
        return JobLease(
            id=row.id, kind=row.kind, enquiry_id=row.enquiry_id, revision=row.revision,
            session_generation=row.session_generation, lease_token=token, expires_at=row.lease_expires_at,
            attempt=row.attempts, payload=row.payload,
        )

    async def renew(self, *, job_id, token, lease_seconds):
        row = self.rows.get(job_id)
        if row is None or row.status != "running" or row.lease_token != token:
            return False
        row.lease_expires_at = WHEN + timedelta(seconds=lease_seconds)
        return True

    async def complete(self, *, job_id, token, result):
        row = self.rows.get(job_id)
        if row is None or row.lease_token != token:
            return False  # expired / reclaimed worker cannot commit
        row.status = result.status
        row.result = result
        return True

    async def current_fence(self, enquiry_id):
        return self.fence

    async def insert_job(self, *, kind, payload, dedupe_key, enquiry_id, revision, session_generation):
        if dedupe_key in self.by_dedupe:
            return self.by_dedupe[dedupe_key]       # dedupe: same key returns the same job
        row = Row(id=uuid4(), kind=kind, payload=payload, dedupe_key=dedupe_key,
                  enquiry_id=enquiry_id, revision=revision, session_generation=session_generation)
        self.rows[row.id] = row
        self.by_dedupe[dedupe_key] = row.id
        return row.id

    async def find_dispatchable(self, now):
        out = []
        for row in self.rows.values():
            if row.status == "pending" and row.available_at <= now and row.lease_token is None:
                out.append(row.id)
            elif row.status == "running" and row.lease_expires_at is not None and row.lease_expires_at < now:
                out.append(row.id)
        return out

    async def reset_to_pending(self, job_id, now):
        row = self.rows[job_id]
        if row.attempts >= row.max_attempts:
            row.status = "failed"            # permanent failure is not retried (F52)
            return False
        row.status = "pending"
        row.lease_token = None
        row.lease_expires_at = None
        return True


class FakeQueue:
    def __init__(self):
        self.pushed: list[UUID] = []

    async def push(self, job_id):
        self.pushed.append(job_id)


class FailingQueue:
    async def push(self, job_id):
        raise RuntimeError("redis down")


def _lease(store_row: Row, token: UUID) -> JobLease:
    return JobLease(
        id=store_row.id, kind=store_row.kind, enquiry_id=store_row.enquiry_id, revision=store_row.revision,
        session_generation=store_row.session_generation, lease_token=token,
        expires_at=WHEN + timedelta(seconds=LEASE_SECONDS), attempt=1, payload=store_row.payload,
    )


class Leases(unittest.IsolatedAsyncioTestCase):
    async def test_claim_sets_fresh_token_and_increments_attempts(self):
        row = Row(id=uuid4(), kind="nameplate")
        store = FakeJobStore([row])
        lease = await claim_job(row.id, "w1", store=store)
        self.assertIsNotNone(lease)
        self.assertEqual(lease.attempt, 1)
        self.assertIsNotNone(lease.lease_token)

    async def test_locked_row_is_skipped(self):  # FOR UPDATE SKIP LOCKED
        row = Row(id=uuid4(), kind="nameplate")
        store = FakeJobStore([row], locked={row.id})
        self.assertIsNone(await claim_job(row.id, "w1", store=store))

    async def test_heartbeat_true_then_false_after_token_change(self):
        row = Row(id=uuid4(), kind="export_pdf")
        store = FakeJobStore([row])
        lease = await claim_job(row.id, "w1", store=store)
        self.assertTrue(await heartbeat(lease, store=store))
        row.lease_token = uuid4()  # another worker reclaimed the lease
        self.assertFalse(await heartbeat(lease, store=store))

    async def test_finish_requires_matching_token(self):  # expired worker cannot commit
        row = Row(id=uuid4(), kind="export_pdf")
        store = FakeJobStore([row])
        lease = await claim_job(row.id, "w1", store=store)
        stale = lease.model_copy(update={"lease_token": uuid4()})
        self.assertFalse(await finish_job(stale, JobResult(status="succeeded", result_id=uuid4(), error_code=None), store=store))

    async def test_finish_fenced_by_current_revision(self):
        enquiry = uuid4()
        row = Row(id=uuid4(), kind="nameplate", enquiry_id=enquiry, revision=1, session_generation=1)
        store = FakeJobStore([row], fence=(2, 1))  # current revision moved to 2
        lease = await claim_job(row.id, "w1", store=store)
        self.assertFalse(await finish_job(lease, JobResult(status="succeeded", result_id=uuid4(), error_code=None), store=store))

    async def test_finish_fenced_by_old_generation(self):  # F05 late OCR from old generation
        enquiry = uuid4()
        row = Row(id=uuid4(), kind="nameplate", enquiry_id=enquiry, revision=1, session_generation=1)
        store = FakeJobStore([row], fence=(1, 2))  # demo reset bumped generation to 2
        lease = await claim_job(row.id, "w1", store=store)
        self.assertFalse(await finish_job(lease, JobResult(status="succeeded", result_id=uuid4(), error_code=None), store=store))

    async def test_finish_succeeds_when_current(self):
        enquiry = uuid4()
        row = Row(id=uuid4(), kind="nameplate", enquiry_id=enquiry, revision=2, session_generation=3)
        store = FakeJobStore([row], fence=(2, 3))
        lease = await claim_job(row.id, "w1", store=store)
        self.assertTrue(await finish_job(lease, JobResult(status="succeeded", result_id=uuid4(), error_code=None), store=store))


class Dispatch(unittest.IsolatedAsyncioTestCase):
    async def test_persist_before_push(self):
        store, queue = FakeJobStore([]), FakeQueue()
        job_id = await enqueue_job(store=store, queue=queue, kind="nameplate", payload={}, dedupe_key="k1")
        self.assertIn(job_id, store.rows)
        self.assertEqual(queue.pushed, [job_id])

    async def test_redis_failure_still_persists_job(self):  # F51 Redis loss does not lose DB job
        store = FakeJobStore([])
        job_id = await enqueue_job(store=store, queue=FailingQueue(), kind="nameplate", payload={}, dedupe_key="k2")
        self.assertIn(job_id, store.rows)  # row persisted despite push failure

    async def test_dedupe_returns_same_job(self):
        store, queue = FakeJobStore([]), FakeQueue()
        a = await enqueue_job(store=store, queue=queue, kind="nameplate", payload={}, dedupe_key="dup")
        b = await enqueue_job(store=store, queue=queue, kind="nameplate", payload={}, dedupe_key="dup")
        self.assertEqual(a, b)

    def test_concurrency_bound_per_kind(self):
        guard = ConcurrencyGuard()
        self.assertTrue(guard.acquire("nameplate"))
        self.assertFalse(guard.can_run("nameplate"))  # one OCR at a time
        guard.release("nameplate")
        self.assertTrue(guard.can_run("nameplate"))

    def test_graceful_shutdown_stops_claiming(self):
        dispatcher = Dispatcher()
        self.assertTrue(dispatcher.should_claim("nameplate"))
        dispatcher.request_shutdown()
        self.assertFalse(dispatcher.should_claim("nameplate"))


class Sweeper(unittest.IsolatedAsyncioTestCase):
    async def test_redispatches_expired_running_job(self):
        row = Row(id=uuid4(), kind="nameplate", status="running", attempts=1,
                  lease_token=uuid4(), lease_expires_at=WHEN - timedelta(seconds=1))
        store, queue = FakeJobStore([row]), FakeQueue()
        count = await sweep_once(WHEN, store=store, queue=queue)
        self.assertEqual(count, 1)
        self.assertEqual(store.rows[row.id].status, "pending")
        self.assertEqual(queue.pushed, [row.id])

    async def test_exhausted_job_is_failed_not_retried(self):  # F52
        row = Row(id=uuid4(), kind="nameplate", status="running", attempts=3, max_attempts=3,
                  lease_token=uuid4(), lease_expires_at=WHEN - timedelta(seconds=1))
        store, queue = FakeJobStore([row]), FakeQueue()
        count = await sweep_once(WHEN, store=store, queue=queue)
        self.assertEqual(count, 0)
        self.assertEqual(store.rows[row.id].status, "failed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
