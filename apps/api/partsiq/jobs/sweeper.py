"""Job sweeper — reclaim expired leases, redispatch, fail exhausted (prompt 15 — F51, F52).

Ported from ``services/worker/app/sweeper.py``. The sweeper runs on a timer inside the
worker and treats the database as the source of truth: it scans for work that should be
dispatchable but is not on the queue — pending jobs whose ``available_at`` has passed with
no live lease, and running jobs whose lease has expired — resets each to pending and
re-pushes a Redis wakeup. This recovers a job after a dead worker or a Redis loss (F51). A
job that has exhausted ``max_attempts`` is marked FAILED rather than retried forever (F52:
a permanent failure is not retried). Returns the number of jobs redispatched.
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from .repository import JobQueue


class SweepStore(Protocol):
    """Injected async sweep port. asyncpg at runtime, fake in tests."""

    async def find_dispatchable(self, now: datetime) -> list[UUID]:
        """Return ids of pending-with-no-lease or running-with-expired-lease jobs."""
        ...

    async def reset_to_pending(self, job_id: UUID, now: datetime) -> bool:
        """Reset to pending for redispatch, or FAIL if ``attempts`` is exhausted.

        Returns ``True`` when the job was reset (and should be re-pushed) and ``False`` when it
        was failed instead (past ``max_attempts``) — a permanent failure is not retried (F52).
        """
        ...


async def sweep_once(now: datetime, *, store: SweepStore, queue: JobQueue) -> int:
    """Reclaim stranded/expired jobs and redispatch them; return how many were redispatched.

    A job past ``max_attempts`` is failed by ``reset_to_pending`` (which returns ``False``) and
    is NOT re-pushed. A queue push failure for a reset job is tolerated: the row stays pending
    and the next sweep retries it, so a Redis outage still never loses the job (F51).
    """
    redispatched = 0
    for job_id in await store.find_dispatchable(now):
        if not await store.reset_to_pending(job_id, now):
            continue  # exhausted -> failed, not retried (F52)
        try:
            await queue.push(job_id)
        except Exception:  # noqa: BLE001 — the next sweep retries; the row stays pending
            continue
        redispatched += 1
    return redispatched
