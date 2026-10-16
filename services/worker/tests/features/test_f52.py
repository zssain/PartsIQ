"""F52 Retry and deduplication — claim with SKIP LOCKED, lease token, fenced final writes.

A locked row is skipped; a claim stamps a fresh token and increments attempts; a heartbeat
renews only while the token is ours; a completion is fenced by token (an expired worker
cannot commit); a job past max_attempts is failed, not retried.
"""
from __future__ import annotations

import unittest
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.leases import claim_job, finish_job, heartbeat
from partsiq_common.contracts import JobLease, JobResult

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


@dataclass
class Row:
    id: UUID
    kind: str = "nameplate"
    status: str = "pending"
    attempts: int = 0
    lease_token: UUID | None = None
    lease_expires_at: datetime | None = None
    enquiry_id: UUID | None = None
    revision: int | None = None
    session_generation: int | None = None
    payload: dict = field(default_factory=dict)


class Store:
    def __init__(self, row, *, locked=False, fence=None):
        self.row = row
        self.locked = locked
        self.fence = fence

    async def claim(self, *, job_id, worker_id, token, lease_seconds):
        if self.locked or self.row.id != job_id or self.row.status not in ("pending",):
            return None
        self.row.status = "running"
        self.row.lease_token = token
        self.row.attempts += 1
        self.row.lease_expires_at = NOW + timedelta(seconds=lease_seconds)
        return JobLease(
            id=self.row.id, kind=self.row.kind, enquiry_id=self.row.enquiry_id, revision=self.row.revision,
            session_generation=self.row.session_generation, lease_token=token,
            expires_at=self.row.lease_expires_at, attempt=self.row.attempts, payload=self.row.payload,
        )

    async def renew(self, *, job_id, token, lease_seconds):
        return self.row.status == "running" and self.row.lease_token == token

    async def complete(self, *, job_id, token, result):
        if self.row.lease_token != token:
            return False
        self.row.status = result.status
        return True

    async def current_fence(self, enquiry_id):
        return self.fence


def _ok():
    return JobResult(status="succeeded", result_id=uuid4(), error_code=None)


class RetryAndDedup(unittest.IsolatedAsyncioTestCase):
    async def test_claim_increments_attempts_with_token(self):  # success
        store = Store(Row(id=uuid4()))
        lease = await claim_job(store.row.id, "w1", store=store)
        self.assertIsNotNone(lease)
        self.assertEqual(store.row.attempts, 1)

    async def test_locked_row_skipped(self):
        store = Store(Row(id=uuid4()), locked=True)
        self.assertIsNone(await claim_job(store.row.id, "w1", store=store))

    async def test_expired_worker_cannot_commit(self):
        store = Store(Row(id=uuid4()))
        lease = await claim_job(store.row.id, "w1", store=store)
        store.row.lease_token = uuid4()  # reclaimed by the sweeper/another worker
        self.assertFalse(await finish_job(lease, _ok(), store=store))

    async def test_heartbeat_tracks_ownership(self):
        store = Store(Row(id=uuid4()))
        lease = await claim_job(store.row.id, "w1", store=store)
        self.assertTrue(await heartbeat(lease, store=store))
        store.row.lease_token = uuid4()
        self.assertFalse(await heartbeat(lease, store=store))

    async def test_stale_revision_result_fenced(self):  # stale-revision
        enquiry = uuid4()
        store = Store(Row(id=uuid4(), enquiry_id=enquiry, revision=1, session_generation=1), fence=(2, 1))
        lease = await claim_job(store.row.id, "w1", store=store)
        self.assertFalse(await finish_job(lease, _ok(), store=store))


if __name__ == "__main__":
    unittest.main(verbosity=2)
