"""Jobs persistence port + durable lease operations (prompt 15 — F51, F52, F05).

Ported and consolidated from the legacy worker: ``services/worker/app/leases.py`` (claim /
heartbeat / finish fenced by token + revision + generation) and the persist-before-Redis
``enqueue_job`` from ``services/worker/app/dispatcher.py``. There is no separate worker
service any more — the same ``partsiq`` package supplies these domain functions, and an
asyncpg-backed adapter implements the :class:`JobStore` / :class:`DispatchStore` ports at
runtime. Unit tests inject :class:`InMemoryJobStore`, which mirrors the SAME fencing and
dedupe rules so the logic is testable offline; the live asyncpg path is BLOCKED here.

Lease lifecycle (F52):
* ``claim_job`` takes the row with ``FOR UPDATE SKIP LOCKED``, stamps a FRESH random fencing
  token and increments ``attempts`` (so a second worker cannot also hold it). A row held by
  another worker (locked) or already terminal is skipped — ``None`` is returned.
* ``heartbeat`` renews the lease only while the token still matches; once reclaimed it is
  ``False`` and the worker must stop.
* ``finish_job`` commits a terminal result only when the lease token is STILL ours AND, for
  an enquiry-bound job, the enquiry's current revision and demo session generation still
  match the lease. A late result from a superseded revision (F52) or an old demo generation
  (F05) is DISCARDED, never committed over current data.

Enqueue (F51):
* ``enqueue_job`` inserts the durable job row FIRST (idempotent by ``dedupe_key``) and only
  then best-effort pushes a Redis wakeup. A push failure is tolerated — the database is the
  source of truth and the sweeper redispatches, so a Redis loss never loses the job.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid4

from partsiq.core.contracts import JobLease, JobResult
from partsiq.core.settings import load_settings

JobStatus = str


def _lease_seconds() -> int:
    """The configured lease duration (JOB_LEASE_SECONDS), defaulting safely offline."""
    try:
        return load_settings().job_lease_seconds
    except Exception:  # noqa: BLE001 — settings unavailable offline must not break the port
        return 120


# ----------------------------------------------------------------------------- ports


class JobStore(Protocol):
    """Injected async lease port. asyncpg (FOR UPDATE SKIP LOCKED) at runtime, fake in tests."""

    async def claim(
        self, *, job_id: UUID, worker_id: str, token: UUID, lease_seconds: int, now: datetime
    ) -> JobLease | None:
        """Claim a pending/expired row, stamp ``token``, bump ``attempts``; ``None`` if taken."""
        ...

    async def renew(self, *, job_id: UUID, token: UUID, lease_seconds: int, now: datetime) -> bool:
        """Renew the lease expiry while the token is still ours; ``False`` otherwise."""
        ...

    async def complete(self, *, job_id: UUID, token: UUID, result: JobResult) -> bool:
        """Write the terminal result only if the lease token still matches."""
        ...

    async def current_fence(self, enquiry_id: UUID) -> tuple[int | None, int | None] | None:
        """Return the enquiry's current ``(revision, session_generation)`` or ``None``."""
        ...


class DispatchStore(Protocol):
    """Injected async enqueue port. The insert is idempotent on ``dedupe_key``."""

    async def insert_job(
        self,
        *,
        kind: str,
        payload: dict,
        dedupe_key: str,
        enquiry_id: UUID | None,
        revision: int | None,
        session_generation: int | None,
    ) -> UUID:
        """Insert the durable row; return the existing id on a duplicate ``dedupe_key``."""
        ...


class JobQueue(Protocol):
    """Redis-like wakeup port. A push failure is tolerated (database is the source of truth)."""

    async def push(self, job_id: UUID) -> None:
        ...


# --------------------------------------------------------------------------- domain ops


async def claim_job(job_id: UUID, worker_id: str, *, store: JobStore) -> JobLease | None:
    """Claim a due job with a fresh fencing token; ``None`` if it could not be taken (F52).

    The fresh ``uuid4`` token fences out any prior holder: once this claim lands, a stale
    worker's heartbeat/finish will no longer match. ``attempts`` is incremented inside the
    same locked claim so the sweeper's max-attempts ceiling is honoured.
    """
    return await store.claim(
        job_id=job_id,
        worker_id=worker_id,
        token=uuid4(),
        lease_seconds=_lease_seconds(),
        now=datetime.now(UTC),
    )


async def heartbeat(lease: JobLease, *, store: JobStore) -> bool:
    """Renew the lease; ``False`` once the token is no longer ours (the lease was lost)."""
    return await store.renew(
        job_id=lease.id,
        token=lease.lease_token,
        lease_seconds=_lease_seconds(),
        now=datetime.now(UTC),
    )


async def finish_job(lease: JobLease, result: JobResult, *, store: JobStore) -> bool:
    """Commit a terminal result only if the lease is still valid AND the enquiry is unchanged.

    Fencing order mirrors the workflow commit (F50/F52/F05): first the enquiry's current
    revision/generation must still match the lease (a newer revision or a bumped demo
    generation supersedes this work), then the lease token must still be current. Either
    mismatch returns ``False`` and nothing is written.
    """
    if lease.enquiry_id is not None:
        fence = await store.current_fence(lease.enquiry_id)
        if fence is None:
            return False  # the enquiry is gone; the result cannot land
        current_revision, current_generation = fence
        if lease.revision is not None and lease.revision != current_revision:
            return False  # a newer revision supersedes this result (F52)
        if lease.session_generation is not None and lease.session_generation != current_generation:
            return False  # a demo reset bumped the generation; old work cannot land (F05)
    return await store.complete(job_id=lease.id, token=lease.lease_token, result=result)


async def enqueue_job(
    *,
    store: DispatchStore,
    queue: JobQueue,
    kind: str,
    payload: dict,
    dedupe_key: str,
    enquiry_id: UUID | None = None,
    revision: int | None = None,
    session_generation: int | None = None,
) -> UUID:
    """Insert the durable job row first (dedupe-idempotent), then best-effort push to Redis.

    Persist-before-dispatch (F51): the row is the source of truth. A duplicate ``dedupe_key``
    returns the existing job id (no second row, no double publication). A Redis push failure
    is swallowed — the sweeper will redispatch the committed row, so the job is never lost.
    """
    job_id = await store.insert_job(
        kind=kind,
        payload=payload,
        dedupe_key=dedupe_key,
        enquiry_id=enquiry_id,
        revision=revision,
        session_generation=session_generation,
    )
    try:
        await queue.push(job_id)
    except Exception:  # noqa: BLE001 — Redis is dispatch, not truth; the sweeper redispatches
        pass
    return job_id


# ----------------------------------------------------------------- offline in-memory fake


@dataclass
class JobRow:
    """A durable job row as the asyncpg adapter would persist it (mirrored for tests)."""

    id: UUID
    kind: str
    status: JobStatus = "pending"
    attempts: int = 0
    max_attempts: int = 3
    lease_token: UUID | None = None
    lease_expires_at: datetime | None = None
    available_at: datetime | None = None
    enquiry_id: UUID | None = None
    revision: int | None = None
    session_generation: int | None = None
    dedupe_key: str = ""
    payload: dict = field(default_factory=dict)
    result: JobResult | None = None


@dataclass
class InMemoryJobStore:
    """Deterministic in-memory fake mirroring FOR UPDATE SKIP LOCKED, fencing and dedupe.

    It is NOT a database and performs no I/O; it exists so the lease/enqueue/sweep logic can
    be exercised offline with the same semantics the asyncpg adapter must enforce. ``locked``
    holds job ids another transaction is assumed to be editing (SKIP LOCKED); ``fence`` is the
    authoritative current ``(revision, session_generation)`` per enquiry.
    """

    rows: dict[UUID, JobRow] = field(default_factory=dict)
    locked: set[UUID] = field(default_factory=set)
    fence: dict[UUID, tuple[int | None, int | None]] = field(default_factory=dict)
    by_dedupe: dict[str, UUID] = field(default_factory=dict)

    def add(self, row: JobRow) -> JobRow:
        self.rows[row.id] = row
        if row.dedupe_key:
            self.by_dedupe.setdefault(row.dedupe_key, row.id)
        return row

    def set_fence(self, enquiry_id: UUID, revision: int | None, generation: int | None) -> None:
        self.fence[enquiry_id] = (revision, generation)

    async def claim(self, *, job_id, worker_id, token, lease_seconds, now):
        row = self.rows.get(job_id)
        if row is None or job_id in self.locked:  # SKIP LOCKED: another worker holds it
            return None
        expired = (
            row.status == "running"
            and row.lease_expires_at is not None
            and row.lease_expires_at <= now
        )
        if row.status != "pending" and not expired:
            return None
        row.status = "running"
        row.lease_token = token
        row.attempts += 1
        row.lease_expires_at = now + timedelta(seconds=lease_seconds)
        return JobLease(
            id=row.id,
            kind=row.kind,
            enquiry_id=row.enquiry_id,
            revision=row.revision,
            session_generation=row.session_generation,
            lease_token=token,
            expires_at=row.lease_expires_at,
            attempt=row.attempts,
            payload=row.payload,
        )

    async def renew(self, *, job_id, token, lease_seconds, now):
        row = self.rows.get(job_id)
        if row is None or row.status != "running" or row.lease_token != token:
            return False
        row.lease_expires_at = now + timedelta(seconds=lease_seconds)
        return True

    async def complete(self, *, job_id, token, result):
        row = self.rows.get(job_id)
        if row is None or row.lease_token != token:
            return False  # an expired / reclaimed worker cannot commit
        row.status = result.status
        row.result = result
        return True

    async def current_fence(self, enquiry_id):
        return self.fence.get(enquiry_id)

    async def insert_job(
        self, *, kind, payload, dedupe_key, enquiry_id, revision, session_generation
    ):
        if dedupe_key and dedupe_key in self.by_dedupe:
            return self.by_dedupe[dedupe_key]  # dedupe: same key returns the same job
        row = JobRow(
            id=uuid4(),
            kind=kind,
            payload=payload,
            dedupe_key=dedupe_key,
            enquiry_id=enquiry_id,
            revision=revision,
            session_generation=session_generation,
        )
        self.add(row)
        return row.id

    async def find_dispatchable(self, now):
        out: list[UUID] = []
        for row in self.rows.values():
            pending = (
                row.status == "pending"
                and row.lease_token is None
                and (row.available_at is None or row.available_at <= now)
            )
            expired = (
                row.status == "running"
                and row.lease_expires_at is not None
                and row.lease_expires_at < now
            )
            if pending or expired:
                out.append(row.id)
        return out

    async def reset_to_pending(self, job_id, now):
        row = self.rows[job_id]
        if row.attempts >= row.max_attempts:
            row.status = "failed"  # a permanent failure is not retried (F52)
            row.lease_token = None
            row.lease_expires_at = None
            return False
        row.status = "pending"
        row.lease_token = None
        row.lease_expires_at = None
        return True
