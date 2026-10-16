"""Sweeper (prompt 15 — F51, F52).

Contract: ``async def sweep_once(now: datetime) -> int``.

Scans the database (the source of truth) for work that should be dispatchable but is not
on the queue: pending jobs whose ``available_at`` has passed with no live lease, and
running jobs whose lease has expired. Each is reset to pending and re-pushed to Redis so a
Redis loss or a dead worker does not strand a job (F51). A job that has exhausted
``max_attempts`` is marked failed rather than retried forever (F52: a permanent failure is
not retried). The DB/Redis I/O lives behind injected ports; the live adapters are
integration work. Returns the number of jobs redispatched.
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.dispatcher import JobQueue


class SweepStore(Protocol):
    async def find_dispatchable(self, now: datetime) -> list[UUID]: ...

    async def reset_to_pending(self, job_id: UUID, now: datetime) -> bool: ...  # False if exhausted -> failed


async def sweep_once(now: datetime, *, store: SweepStore, queue: JobQueue) -> int:
    """Reclaim stranded/expired jobs and redispatch them; return how many were redispatched."""
    redispatched = 0
    for job_id in await store.find_dispatchable(now):
        if await store.reset_to_pending(job_id, now):
            try:
                await queue.push(job_id)
            except Exception:  # noqa: BLE001 — the next sweep retries; the row stays pending
                continue
            redispatched += 1
    return redispatched
