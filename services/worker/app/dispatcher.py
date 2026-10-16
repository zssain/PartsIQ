"""Job dispatch and bounded concurrency (prompt 15 — F51, F52).

Persist-before-dispatch: a job row is inserted (deduplicated by its ``dedupe_key``) BEFORE
it is pushed to Redis, so a Redis loss never loses the job — the sweeper will redispatch it
from the database, which is the source of truth (F51). Claiming is bounded to one OCR and
one PDF at a time initially (F51: heavy work never starves HTTP intake), and a graceful
shutdown stops claiming new work while letting a held lease finish. The DB/Redis I/O lives
behind injected ports; the live adapters are integration work.
"""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

# Initial bounded concurrency per job kind (ADR-009: small, predictable worker).
CONCURRENCY_LIMITS: dict[str, int] = {"nameplate": 1, "export_pdf": 1}
DEFAULT_LIMIT = 1


class JobQueue(Protocol):
    async def push(self, job_id: UUID) -> None: ...


class DispatchStore(Protocol):
    async def insert_job(
        self,
        *,
        kind: str,
        payload: dict,
        dedupe_key: str,
        enquiry_id: UUID | None,
        revision: int | None,
        session_generation: int | None,
    ) -> UUID: ...  # returns existing id on a duplicate dedupe_key (idempotent enqueue)


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
    """Insert the durable job row first, then best-effort push to Redis."""
    job_id = await store.insert_job(
        kind=kind, payload=payload, dedupe_key=dedupe_key,
        enquiry_id=enquiry_id, revision=revision, session_generation=session_generation,
    )
    try:
        await queue.push(job_id)
    except Exception:  # noqa: BLE001 — Redis is dispatch, not truth; the sweeper redispatches
        pass
    return job_id


class ConcurrencyGuard:
    """Tracks in-flight jobs per kind and enforces the initial per-kind bound."""

    def __init__(self, limits: dict[str, int] | None = None) -> None:
        self._limits = dict(limits or CONCURRENCY_LIMITS)
        self._running: dict[str, int] = {}

    def can_run(self, kind: str) -> bool:
        return self._running.get(kind, 0) < self._limits.get(kind, DEFAULT_LIMIT)

    def acquire(self, kind: str) -> bool:
        if not self.can_run(kind):
            return False
        self._running[kind] = self._running.get(kind, 0) + 1
        return True

    def release(self, kind: str) -> None:
        self._running[kind] = max(0, self._running.get(kind, 0) - 1)


class Dispatcher:
    """Owns the claim gate and the drain flag for graceful shutdown."""

    def __init__(self, guard: ConcurrencyGuard | None = None) -> None:
        self.guard = guard or ConcurrencyGuard()
        self._draining = False

    def request_shutdown(self) -> None:
        self._draining = True

    @property
    def draining(self) -> bool:
        return self._draining

    def should_claim(self, kind: str) -> bool:
        """Claim only when not draining and under the per-kind concurrency bound."""
        return not self._draining and self.guard.can_run(kind)
