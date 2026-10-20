"""Worker entrypoint (prompt 15 — F51, F52, F05).

The worker is NOT a separate service: it imports the SAME ``partsiq`` package as the API and
runs durable jobs from the PostgreSQL ``jobs`` queue. This module owns the worker's runtime
state — the injected job store, queue and the handler registry — plus a drain flag for
graceful shutdown and a readiness gate.

Graceful shutdown (F51): ``request_shutdown`` sets the drain flag; ``should_claim`` then
returns ``False`` so no NEW job is claimed, while a lease already held is allowed to finish
and commit under its fence. Readiness stays ``False`` until both the store and the queue are
wired (``bind``), so an unconfigured worker never reports itself ready. The live asyncpg
store and Redis queue adapters are wired at deploy time; offline they are left unset and
readiness is honestly ``False`` (BLOCKED — not faked).
"""
from __future__ import annotations

from datetime import UTC, datetime

from .handlers import ConcurrencyGuard, get_handler
from .repository import DispatchStore, JobQueue, JobStore
from .sweeper import SweepStore, sweep_once


class Worker:
    """Owns the worker's claim gate, drain flag, concurrency guard and readiness.

    A single process holds one :class:`Worker`. The store/queue are injected via :meth:`bind`
    at startup (asyncpg + Redis at runtime, fakes in tests); until then the worker is not
    ready. The concurrency guard bounds heavy jobs per kind so OCR/PDF never starve intake.
    """

    def __init__(self, *, worker_id: str = "partsiq-worker", guard: ConcurrencyGuard | None = None) -> None:
        self.worker_id = worker_id
        self.guard = guard or ConcurrencyGuard()
        self.store: JobStore | None = None
        self.queue: JobQueue | None = None
        self._draining = False

    def bind(self, *, store: JobStore, queue: JobQueue) -> None:
        """Wire the live/fake job store and queue; the worker becomes ready afterwards."""
        self.store = store
        self.queue = queue

    @property
    def ready(self) -> bool:
        """Readiness is ``False`` until both the store and the queue are wired."""
        return self.store is not None and self.queue is not None

    @property
    def draining(self) -> bool:
        return self._draining

    def request_shutdown(self) -> None:
        """Begin a graceful drain: stop claiming new work, let held leases finish."""
        self._draining = True

    def should_claim(self, kind: str) -> bool:
        """Claim only when ready, not draining, a handler exists, and under the kind's bound."""
        return (
            self.ready
            and not self._draining
            and get_handler(kind) is not None
            and self.guard.can_run(kind)
        )

    async def sweep(self) -> int:
        """Run one sweeper pass over the bound store, redispatching stranded/expired jobs."""
        if self.store is None or self.queue is None:
            return 0
        return await sweep_once(datetime.now(UTC), store=self.store, queue=self.queue)  # type: ignore[arg-type]


# The process-wide worker instance. The deploy entrypoint calls ``worker.bind(...)`` with the
# asyncpg-backed store (implementing JobStore + DispatchStore + SweepStore) and the Redis
# queue, then drives the claim/heartbeat/finish loop and periodic sweeps.
worker = Worker()


async def worker_main() -> None:
    """Deploy entrypoint; a no-op offline because the live store/queue are BLOCKED here.

    At deploy time the caller binds the asyncpg store and Redis queue first; without them the
    worker stays not-ready and does no work rather than spinning against missing dependencies.
    """
    if not worker.ready:
        return
    await worker.sweep()


__all__ = [
    "DispatchStore",
    "JobQueue",
    "JobStore",
    "SweepStore",
    "Worker",
    "worker",
    "worker_main",
]


if __name__ == "__main__":
    # Deploy entrypoint (infra/compose.*.yml). With a database configured this runs the live
    # PostgreSQL + Redis + Storage worker; without one it refuses to start rather than idling.
    from .live import main as _live_main

    _live_main()
