"""F52 Retry & dedup facade (helper ``jobs.retry_failed``).

Re-queues a FAILED background job. Only a job in a terminal ``failed`` state may be retried (a
pending/running/succeeded job is a 409) and only its owner (scoped access; a foreign job is a 404).
The retry is deduplicated two ways: it is idempotent on the request ``Idempotency-Key`` (a
double-click re-queues once) and it carries an ``expected_revision`` so a retry can never apply to
a resource that has since moved on (a stale revision is a 409). Retrying never bypasses a gate —
the re-run goes through the same durable pipeline and the same human publication gate; it only
re-attempts work that failed. Returns the job handle for polling (F51).

Thin adapter over an injected port; the live job store is BLOCKED offline, so the caller gets a
clean 503 rather than a fabricated re-queue.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from partsiq.core.api_models import JobView, RetryRequest
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.features._ops_ports import require_store


@runtime_checkable
class JobRetrySource(Protocol):
    """Scoped job-retry port (authorises the actor and enforces failed-only + dedup)."""

    async def retry_failed(
        self, actor: ActorContext, job_id: UUID, expected_revision: int, key: UUID
    ) -> JobView: ...


async def retry_failed(
    actor: ActorContext,
    job_id: UUID,
    request: RetryRequest,
    key: UUID,
    *,
    container: AppContainer,
    source: JobRetrySource | None = None,
) -> JobView:
    """Re-queue a failed job the caller owns; failed-only, revision-checked, deduped (scoped)."""
    source = source or require_store(container, "jobs")
    return await source.retry_failed(actor, job_id, request.expected_revision, key)
