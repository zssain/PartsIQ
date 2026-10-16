"""F51 Background jobs — persist before Redis dispatch; Redis loss never loses a DB job.

The job row is the source of truth: it is inserted before the Redis push, survives a push
failure, and the sweeper redispatches pending/expired work. Worker job kinds cover OCR,
PDF, imports and cleanup. (The Redis-unavailable rate-limiter "fail closed" case belongs to
the gateway limiter, prompt 08, not the worker.)
"""
from __future__ import annotations

import unittest
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.dispatcher import CONCURRENCY_LIMITS, ConcurrencyGuard, enqueue_job
from app.sweeper import sweep_once


@dataclass
class Row:
    id: UUID
    kind: str
    status: str = "pending"
    attempts: int = 0
    max_attempts: int = 3
    lease_token: UUID | None = None
    lease_expires_at: datetime | None = None
    available_at: datetime = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
    dedupe_key: str = ""
    payload: dict = field(default_factory=dict)


NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


class Store:
    def __init__(self, rows=None):
        self.rows = {r.id: r for r in (rows or [])}
        self.by_dedupe = {r.dedupe_key: r.id for r in self.rows.values() if r.dedupe_key}

    async def insert_job(self, *, kind, payload, dedupe_key, enquiry_id, revision, session_generation):
        if dedupe_key in self.by_dedupe:
            return self.by_dedupe[dedupe_key]
        row = Row(id=uuid4(), kind=kind, payload=payload, dedupe_key=dedupe_key)
        self.rows[row.id] = row
        self.by_dedupe[dedupe_key] = row.id
        return row.id

    async def find_dispatchable(self, now):
        return [r.id for r in self.rows.values()
                if (r.status == "pending" and r.lease_token is None)
                or (r.status == "running" and r.lease_expires_at and r.lease_expires_at < now)]

    async def reset_to_pending(self, job_id, now):
        row = self.rows[job_id]
        if row.attempts >= row.max_attempts:
            row.status = "failed"
            return False
        row.status, row.lease_token, row.lease_expires_at = "pending", None, None
        return True


class Queue:
    def __init__(self):
        self.pushed = []

    async def push(self, job_id):
        self.pushed.append(job_id)


class FailingQueue:
    async def push(self, job_id):
        raise RuntimeError("redis down")


class BackgroundJobs(unittest.IsolatedAsyncioTestCase):
    async def test_persist_then_dispatch(self):  # success
        store, queue = Store(), Queue()
        job_id = await enqueue_job(store=store, queue=queue, kind="export_pdf", payload={}, dedupe_key="e1")
        self.assertIn(job_id, store.rows)
        self.assertEqual(queue.pushed, [job_id])

    async def test_redis_loss_keeps_db_job(self):  # dependency-failure
        store = Store()
        job_id = await enqueue_job(store=store, queue=FailingQueue(), kind="nameplate", payload={}, dedupe_key="e2")
        self.assertIn(job_id, store.rows)

    async def test_sweeper_redispatches_pending(self):
        row = Row(id=uuid4(), kind="catalog_import")
        store, queue = Store([row]), Queue()
        self.assertEqual(await sweep_once(NOW, store=store, queue=queue), 1)
        self.assertEqual(queue.pushed, [row.id])

    async def test_expired_running_job_redispatched(self):
        row = Row(id=uuid4(), kind="storage_cleanup", status="running", attempts=1,
                  lease_token=uuid4(), lease_expires_at=NOW - timedelta(seconds=5))
        store, queue = Store([row]), Queue()
        self.assertEqual(await sweep_once(NOW, store=store, queue=queue), 1)

    def test_bounded_concurrency_protects_intake(self):
        guard = ConcurrencyGuard()
        self.assertEqual(CONCURRENCY_LIMITS, {"nameplate": 1, "export_pdf": 1})
        self.assertTrue(guard.acquire("export_pdf"))
        self.assertFalse(guard.can_run("export_pdf"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
