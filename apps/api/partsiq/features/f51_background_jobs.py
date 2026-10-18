"""F51 Background jobs facade (helper ``jobs.get_status``).

Returns the status of a single background job (nameplate OCR, export, catalogue import/publish,
summary, eval, analytics sync, ...): its state, kind, attempt count, any error code and the id of
the resource it produces. Access is ``scoped`` — the store authorises the caller against the job's
owning resource (the enquiry/session that enqueued it, or a staff/admin scope for ops jobs), so a
caller reading a job for a resource they do not own gets NOT_FOUND (404), never another caller's
job. It is read-only: polling a job never advances or mutates it.

Thin adapter over an injected port; the live job store is BLOCKED offline, so the caller gets a
clean 503 rather than a fabricated job state.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from partsiq.core.api_models import JobView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.features._ops_ports import require_store


@runtime_checkable
class JobStatusSource(Protocol):
    """Scoped job-status read port (authorises the actor against the job's owning resource)."""

    async def get_status(self, actor: ActorContext, job_id: UUID) -> JobView: ...


async def get_status(
    actor: ActorContext,
    job_id: UUID,
    *,
    container: AppContainer,
    source: JobStatusSource | None = None,
) -> JobView:
    """Return the status of a job the caller owns (scoped access; foreign job -> 404)."""
    source = source or require_store(container, "jobs")
    return await source.get_status(actor, job_id)
