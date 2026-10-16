"""Durable job leases (prompt 15 — F51, F52).

Contracts:
    async def claim_job(job_id: UUID, worker_id: str) -> JobLease | None
    async def heartbeat(lease: JobLease) -> bool
    async def finish_job(lease: JobLease, result: JobResult) -> bool

A claim takes the row with ``FOR UPDATE SKIP LOCKED``, stamps a FRESH lease token and
increments ``attempts`` (so a second worker cannot also hold it). A heartbeat renews the
lease only while the token still matches. A completion is fenced three ways (F52/F05): the
lease token must still be current (an expired/reclaimed worker cannot commit) AND, for an
enquiry-bound job, the enquiry's current revision and session generation must still match
the lease — a late result from a superseded revision or an old demo generation cannot
overwrite current data. The DB/Redis I/O lives behind the injected ``JobStore`` port so the
fencing logic is testable offline; the live asyncpg adapter is integration work.
"""
from __future__ import annotations

from typing import Protocol
from uuid import UUID, uuid4

from partsiq_common.contracts import JobLease, JobResult

LEASE_SECONDS = 45
HEARTBEAT_SECONDS = 10


class JobStore(Protocol):
    async def claim(self, *, job_id: UUID, worker_id: str, token: UUID, lease_seconds: int) -> JobLease | None: ...

    async def renew(self, *, job_id: UUID, token: UUID, lease_seconds: int) -> bool: ...

    async def complete(self, *, job_id: UUID, token: UUID, result: JobResult) -> bool: ...

    async def current_fence(self, enquiry_id: UUID) -> tuple[int | None, int | None] | None: ...


async def claim_job(job_id: UUID, worker_id: str, *, store: JobStore) -> JobLease | None:
    """Claim a pending/expired job with a fresh fencing token; None if it could not be taken."""
    return await store.claim(job_id=job_id, worker_id=worker_id, token=uuid4(), lease_seconds=LEASE_SECONDS)


async def heartbeat(lease: JobLease, *, store: JobStore) -> bool:
    """Renew the lease; False once the token is no longer ours (the lease was lost)."""
    return await store.renew(job_id=lease.id, token=lease.lease_token, lease_seconds=LEASE_SECONDS)


async def finish_job(lease: JobLease, result: JobResult, *, store: JobStore) -> bool:
    """Commit a terminal result only if the lease is still valid AND the enquiry is unchanged."""
    if lease.enquiry_id is not None:
        fence = await store.current_fence(lease.enquiry_id)
        if fence is None:
            return False
        current_revision, current_generation = fence
        if lease.revision is not None and lease.revision != current_revision:
            return False  # a newer revision supersedes this result
        if lease.session_generation is not None and lease.session_generation != current_generation:
            return False  # a demo reset bumped the generation; old work cannot land (F05)
    return await store.complete(job_id=lease.id, token=lease.lease_token, result=result)
