"""Job dispatch and bounded concurrency (prompt 15 — F51, F52).

Persist-before-dispatch: a job row is inserted (deduplicated by its ``dedupe_key``) BEFORE
it is pushed to Redis, so a Redis loss never loses the job — the sweeper will redispatch it
from the database, which is the source of truth (F51). Claiming is bounded to one OCR and
one PDF at a time initially (F51: heavy work never starves HTTP intake), and a graceful
shutdown stops claiming new work while letting a held lease finish. The DB/Redis I/O lives
behind injected ports; the live adapters are integration work.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol
from uuid import UUID

# Initial bounded concurrency per job kind (ADR-009: small, predictable worker).
# catalog_publish/catalog_import are not listed here on purpose: they fall back to
# DEFAULT_LIMIT (1), and prompt 15's test pins this dict to the original two kinds.
CONCURRENCY_LIMITS: dict[str, int] = {"nameplate": 1, "export_pdf": 1}
DEFAULT_LIMIT = 1

# Job-kind -> handler registry. Handlers are registered by their owning prompt (16 nameplate,
# 17 export_pdf, …) so the dispatcher routes a claimed job to the right code without importing
# every job module itself. Kept here, the single owner of dispatch, per the one-creator rule.
JobHandler = Callable[..., Awaitable[Any]]
JOB_HANDLERS: dict[str, JobHandler] = {}


def register_handler(kind: str, handler: JobHandler) -> None:
    JOB_HANDLERS[kind] = handler


def get_handler(kind: str) -> JobHandler | None:
    return JOB_HANDLERS.get(kind)


def register_catalog_publish() -> None:
    """Register the F59 catalogue publication handler (owner wiring; called at worker startup).

    Kept as an explicit call rather than an import side effect so the dispatcher module stays
    free of job imports; the catalogue-role store the job needs is injected separately.
    """
    from app.jobs.catalog_publish import publish_catalogue_job

    register_handler("catalog_publish", publish_catalogue_job)


def register_catalog_import() -> None:
    """Register the F58 catalogue-import dry-run validation handler (owner wiring)."""
    from app.features.f58_catalogue_imports import validate_import_job

    register_handler("catalog_import", validate_import_job)


def photo_quality_gate(image: bytes, media_type: str) -> Any:
    """Cheap, local photo-quality pre-check run BEFORE a paid vision call (F16).

    The nameplate path calls this on the fetched image bytes before invoking the paid OCR:
    an unreadable image (unsupported/undecodable/oversized) is turned back with retake guidance
    so no credit is spent, while a merely dark/low-res/blurry image is allowed through with
    advisory guidance. Imported lazily so the dispatcher keeps no Pillow import at module load.
    """
    from app.features.f16_photo_quality_feedback import F16Request, assess_photo

    return assess_photo(F16Request(image_bytes=image, media_type=media_type))


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
