"""Foundation 15 acceptance: durable worker leases, retries and cleanup (F51, F52, F05).

Ports the behaviour characterized in the legacy worker tests
(``services/worker/tests/features/test_f51.py`` and ``test_f52.py``) onto the single
``partsiq`` package. The worker imports the SAME package as the API; its jobs are
lease-fenced.

Deterministic and fully offline: the live asyncpg store (FOR UPDATE SKIP LOCKED) and the
live Redis queue are BLOCKED. ``InMemoryJobStore`` mirrors claim/heartbeat/finish fencing,
dedupe and sweep semantics; fake queues stand in for Redis. The live-infra paths are SKIPPED,
never faked.

Covered behaviours:
  * claim stamps a FRESH fencing token and increments ``attempts``; a locked row is skipped
    (FOR UPDATE SKIP LOCKED); an expired running lease is reclaimable (F52).
  * heartbeat renews only while the token is ours; it is ``False`` once reclaimed (F52).
  * finish is rejected when the lease token changed (expired worker), when the enquiry
    revision changed (F52) and when the demo session generation changed (F05); it succeeds
    only when token + revision + generation all still match.
  * enqueue persists the durable row BEFORE the Redis push, is dedupe-idempotent, and a
    Redis push failure does not lose the job (F51).
  * the concurrency guard bounds concurrent nameplate/export (F51).
  * the sweeper reclaims an expired lease and redispatches it, but fails a job past
    ``max_attempts`` rather than retrying it forever (F52).
  * the worker is not ready until store+queue are wired and a drain flag stops new claims.
"""
from __future__ import annotations

import os
import unittest
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from partsiq.core.contracts import JobResult
from partsiq.jobs.handlers import (
    CONCURRENCY_LIMITS,
    JOB_KINDS,
    ConcurrencyGuard,
    clear_handlers,
    get_handler,
    register_handler,
    registered_kinds,
)
from partsiq.jobs.main import Worker
from partsiq.jobs.repository import (
    InMemoryJobStore,
    JobRow,
    claim_job,
    enqueue_job,
    finish_job,
    heartbeat,
)
from partsiq.jobs.sweeper import sweep_once

WHEN = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


class FakeQueue:
    def __init__(self) -> None:
        self.pushed: list = []

    async def push(self, job_id) -> None:
        self.pushed.append(job_id)


class FailingQueue:
    async def push(self, job_id) -> None:
        raise RuntimeError("redis down")


def _ok() -> JobResult:
    return JobResult(status="succeeded", result_id=uuid4(), error_code=None)


# NOTE: claim_job/heartbeat use datetime.now(UTC) for the lease clock; the InMemoryJobStore
# records whatever ``now`` it is handed, so claims made "now" have a future expiry relative to
# the fixed WHEN sweep time used below.


class Leases(unittest.IsolatedAsyncioTestCase):
    async def test_claim_sets_fresh_token_and_increments_attempts(self):  # success
        row = JobRow(id=uuid4(), kind="nameplate")
        store = InMemoryJobStore()
        store.add(row)
        lease = await claim_job(row.id, "w1", store=store)
        self.assertIsNotNone(lease)
        assert lease is not None
        self.assertEqual(lease.attempt, 1)
        self.assertEqual(store.rows[row.id].attempts, 1)
        self.assertEqual(store.rows[row.id].lease_token, lease.lease_token)

    async def test_locked_row_is_skipped(self):  # FOR UPDATE SKIP LOCKED
        row = JobRow(id=uuid4(), kind="nameplate")
        store = InMemoryJobStore(locked={row.id})
        store.add(row)
        self.assertIsNone(await claim_job(row.id, "w1", store=store))

    async def test_expired_running_lease_is_reclaimable(self):
        row = JobRow(
            id=uuid4(),
            kind="nameplate",
            status="running",
            attempts=1,
            lease_token=uuid4(),
            lease_expires_at=WHEN - timedelta(seconds=1),
        )
        original_token = row.lease_token
        store = InMemoryJobStore()
        store.add(row)
        lease = await claim_job(row.id, "w2", store=store)
        self.assertIsNotNone(lease)
        assert lease is not None
        self.assertEqual(lease.attempt, 2)  # attempts carried forward + 1
        self.assertNotEqual(lease.lease_token, original_token)  # token rotated

    async def test_heartbeat_true_then_false_after_token_change(self):
        row = JobRow(id=uuid4(), kind="export_pdf")
        store = InMemoryJobStore()
        store.add(row)
        lease = await claim_job(row.id, "w1", store=store)
        assert lease is not None
        self.assertTrue(await heartbeat(lease, store=store))
        store.rows[row.id].lease_token = uuid4()  # another worker reclaimed the lease
        self.assertFalse(await heartbeat(lease, store=store))

    async def test_finish_requires_matching_token(self):  # expired worker cannot commit
        row = JobRow(id=uuid4(), kind="export_pdf")
        store = InMemoryJobStore()
        store.add(row)
        lease = await claim_job(row.id, "w1", store=store)
        assert lease is not None
        stale = lease.model_copy(update={"lease_token": uuid4()})
        self.assertFalse(await finish_job(stale, _ok(), store=store))

    async def test_finish_fenced_by_current_revision(self):  # F52 stale revision
        enquiry = uuid4()
        row = JobRow(id=uuid4(), kind="nameplate", enquiry_id=enquiry, revision=1, session_generation=1)
        store = InMemoryJobStore()
        store.add(row)
        store.set_fence(enquiry, revision=2, generation=1)  # current revision moved to 2
        lease = await claim_job(row.id, "w1", store=store)
        assert lease is not None
        self.assertFalse(await finish_job(lease, _ok(), store=store))

    async def test_finish_fenced_by_old_generation(self):  # F05 late OCR from old generation
        enquiry = uuid4()
        row = JobRow(id=uuid4(), kind="nameplate", enquiry_id=enquiry, revision=1, session_generation=1)
        store = InMemoryJobStore()
        store.add(row)
        store.set_fence(enquiry, revision=1, generation=2)  # demo reset bumped generation to 2
        lease = await claim_job(row.id, "w1", store=store)
        assert lease is not None
        self.assertFalse(await finish_job(lease, _ok(), store=store))

    async def test_finish_fenced_when_enquiry_gone(self):
        enquiry = uuid4()
        row = JobRow(id=uuid4(), kind="nameplate", enquiry_id=enquiry, revision=1, session_generation=1)
        store = InMemoryJobStore()
        store.add(row)  # no fence set for the enquiry -> current_fence returns None
        lease = await claim_job(row.id, "w1", store=store)
        assert lease is not None
        self.assertFalse(await finish_job(lease, _ok(), store=store))

    async def test_finish_succeeds_when_current(self):
        enquiry = uuid4()
        row = JobRow(id=uuid4(), kind="nameplate", enquiry_id=enquiry, revision=2, session_generation=3)
        store = InMemoryJobStore()
        store.add(row)
        store.set_fence(enquiry, revision=2, generation=3)
        lease = await claim_job(row.id, "w1", store=store)
        assert lease is not None
        self.assertTrue(await finish_job(lease, _ok(), store=store))
        self.assertEqual(store.rows[row.id].status, "succeeded")

    async def test_finish_non_enquiry_job_only_token_fenced(self):
        row = JobRow(id=uuid4(), kind="catalog_sync")  # no enquiry -> no revision/generation fence
        store = InMemoryJobStore()
        store.add(row)
        lease = await claim_job(row.id, "w1", store=store)
        assert lease is not None
        self.assertTrue(await finish_job(lease, _ok(), store=store))


class Dispatch(unittest.IsolatedAsyncioTestCase):
    async def test_persist_before_push(self):  # success, F51
        store, queue = InMemoryJobStore(), FakeQueue()
        job_id = await enqueue_job(store=store, queue=queue, kind="nameplate", payload={}, dedupe_key="k1")
        self.assertIn(job_id, store.rows)
        self.assertEqual(queue.pushed, [job_id])

    async def test_redis_failure_still_persists_job(self):  # F51 Redis loss keeps DB job
        store = InMemoryJobStore()
        job_id = await enqueue_job(store=store, queue=FailingQueue(), kind="nameplate", payload={}, dedupe_key="k2")
        self.assertIn(job_id, store.rows)  # row persisted despite push failure

    async def test_dedupe_returns_same_job(self):  # F52 deduplication
        store, queue = InMemoryJobStore(), FakeQueue()
        a = await enqueue_job(store=store, queue=queue, kind="nameplate", payload={}, dedupe_key="dup")
        b = await enqueue_job(store=store, queue=queue, kind="nameplate", payload={}, dedupe_key="dup")
        self.assertEqual(a, b)
        self.assertEqual(len(store.rows), 1)  # one row, not two


class Concurrency(unittest.TestCase):
    def test_limits_pin_nameplate_and_export(self):
        self.assertEqual(CONCURRENCY_LIMITS, {"nameplate": 1, "export_pdf": 1})

    def test_concurrency_bound_per_kind(self):  # F51 heavy work never starves intake
        guard = ConcurrencyGuard()
        self.assertTrue(guard.acquire("nameplate"))
        self.assertFalse(guard.can_run("nameplate"))  # one OCR at a time
        self.assertFalse(guard.acquire("nameplate"))
        guard.release("nameplate")
        self.assertTrue(guard.can_run("nameplate"))

    def test_export_and_nameplate_bound_independently(self):
        guard = ConcurrencyGuard()
        self.assertTrue(guard.acquire("export_pdf"))
        self.assertTrue(guard.acquire("nameplate"))  # a different kind still has a slot
        self.assertFalse(guard.can_run("export_pdf"))
        self.assertFalse(guard.can_run("nameplate"))


class Handlers(unittest.TestCase):
    def setUp(self) -> None:
        self.addCleanup(clear_handlers)
        clear_handlers()

    def test_register_and_get_handler(self):
        async def _h(*_a, **_k):
            return None

        register_handler("nameplate", _h)
        self.assertIs(get_handler("nameplate"), _h)
        self.assertIn("nameplate", registered_kinds())

    def test_unknown_kind_rejected(self):
        async def _h(*_a, **_k):
            return None

        with self.assertRaises(ValueError):
            register_handler("not_a_kind", _h)

    def test_all_eight_kinds_are_allowlisted(self):
        self.assertEqual(
            JOB_KINDS,
            frozenset(
                {
                    "nameplate",
                    "export_pdf",
                    "catalog_import",
                    "catalog_publish",
                    "storage_cleanup",
                    "workflow",
                    "analytics_sync",
                    "catalog_sync",
                }
            ),
        )

    def test_unregistered_kind_has_no_handler(self):
        self.assertIsNone(get_handler("export_pdf"))


class Sweeper(unittest.IsolatedAsyncioTestCase):
    async def test_redispatches_expired_running_job(self):  # F51
        row = JobRow(
            id=uuid4(),
            kind="nameplate",
            status="running",
            attempts=1,
            lease_token=uuid4(),
            lease_expires_at=WHEN - timedelta(seconds=1),
        )
        store, queue = InMemoryJobStore(), FakeQueue()
        store.add(row)
        count = await sweep_once(WHEN, store=store, queue=queue)
        self.assertEqual(count, 1)
        self.assertEqual(store.rows[row.id].status, "pending")
        self.assertEqual(queue.pushed, [row.id])

    async def test_redispatches_stranded_pending_job(self):  # F51 Redis loss stranded a row
        row = JobRow(id=uuid4(), kind="catalog_import", status="pending", available_at=WHEN)
        store, queue = InMemoryJobStore(), FakeQueue()
        store.add(row)
        count = await sweep_once(WHEN, store=store, queue=queue)
        self.assertEqual(count, 1)
        self.assertEqual(queue.pushed, [row.id])

    async def test_exhausted_job_is_failed_not_retried(self):  # F52 permanent failure
        row = JobRow(
            id=uuid4(),
            kind="nameplate",
            status="running",
            attempts=3,
            max_attempts=3,
            lease_token=uuid4(),
            lease_expires_at=WHEN - timedelta(seconds=1),
        )
        store, queue = InMemoryJobStore(), FakeQueue()
        store.add(row)
        count = await sweep_once(WHEN, store=store, queue=queue)
        self.assertEqual(count, 0)
        self.assertEqual(store.rows[row.id].status, "failed")
        self.assertEqual(queue.pushed, [])

    async def test_sweep_tolerates_queue_push_failure(self):  # F51 Redis still down during sweep
        row = JobRow(
            id=uuid4(),
            kind="nameplate",
            status="running",
            attempts=1,
            lease_token=uuid4(),
            lease_expires_at=WHEN - timedelta(seconds=1),
        )
        store = InMemoryJobStore()
        store.add(row)
        count = await sweep_once(WHEN, store=store, queue=FailingQueue())
        self.assertEqual(count, 0)  # not counted as redispatched
        self.assertEqual(store.rows[row.id].status, "pending")  # but the row is reset for next sweep


class WorkerLifecycle(unittest.IsolatedAsyncioTestCase):
    def test_not_ready_until_bound(self):
        w = Worker()
        self.assertFalse(w.ready)
        self.assertFalse(w.should_claim("nameplate"))

    def test_ready_after_bind_and_handler_gates_claim(self):
        self.addCleanup(clear_handlers)
        clear_handlers()
        w = Worker()
        w.bind(store=InMemoryJobStore(), queue=FakeQueue())
        self.assertTrue(w.ready)
        # No handler registered yet -> cannot claim.
        self.assertFalse(w.should_claim("nameplate"))

        async def _h(*_a, **_k):
            return None

        register_handler("nameplate", _h)
        self.assertTrue(w.should_claim("nameplate"))

    def test_graceful_shutdown_stops_claiming(self):  # F51 drain flag
        self.addCleanup(clear_handlers)
        clear_handlers()

        async def _h(*_a, **_k):
            return None

        register_handler("nameplate", _h)
        w = Worker()
        w.bind(store=InMemoryJobStore(), queue=FakeQueue())
        self.assertTrue(w.should_claim("nameplate"))
        w.request_shutdown()
        self.assertTrue(w.draining)
        self.assertFalse(w.should_claim("nameplate"))

    def test_concurrency_bound_blocks_claim(self):
        self.addCleanup(clear_handlers)
        clear_handlers()

        async def _h(*_a, **_k):
            return None

        register_handler("nameplate", _h)
        w = Worker()
        w.bind(store=InMemoryJobStore(), queue=FakeQueue())
        self.assertTrue(w.guard.acquire("nameplate"))
        self.assertFalse(w.should_claim("nameplate"))  # at the per-kind bound

    async def test_sweep_through_worker(self):
        row = JobRow(
            id=uuid4(),
            kind="nameplate",
            status="running",
            attempts=1,
            lease_token=uuid4(),
            lease_expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        store, queue = InMemoryJobStore(), FakeQueue()
        store.add(row)
        w = Worker()
        w.bind(store=store, queue=queue)
        count = await w.sweep()
        self.assertEqual(count, 1)
        self.assertEqual(queue.pushed, [row.id])

    async def test_sweep_no_op_when_unbound(self):
        self.assertEqual(await Worker().sweep(), 0)


@unittest.skipUnless(
    os.environ.get("PARTSIQ_LIVE_INFRA") == "1",
    "live asyncpg + Redis are BLOCKED offline; integration run only when PARTSIQ_LIVE_INFRA=1",
)
class LiveInfra(unittest.IsolatedAsyncioTestCase):  # pragma: no cover - integration gate
    async def test_asyncpg_skip_locked_claim(self):
        self.fail("live asyncpg FOR UPDATE SKIP LOCKED adapter is integration work (BLOCKED)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
