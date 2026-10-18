"""F67 Traces facade (helper ``observability.list_stages``).

Returns the per-stage execution trace for an enquiry's current revision — each pipeline stage with
its start, duration, status and any error code — so a reviewer can see WHERE a run spent time or
failed. Trace payloads are redacted by :mod:`partsiq.core.observability` before they are persisted
(no reply prose, citation text, signed URL or secret ever rides a stage), and this read surfaces
them as-is; it never re-runs a stage. Access is ``review``; a foreign/unassigned actor gets
NOT_FOUND (404) and a non-staff (demo) caller is refused by the role gate first.

Thin adapter over an injected port; the live trace store is BLOCKED offline, so a reviewer gets a
clean 503 rather than a fabricated trace.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from partsiq.core.api_models import TraceView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.features._ops_ports import require_store
from partsiq.features.f36_staff_inbox import require_staff_role


@runtime_checkable
class TraceSource(Protocol):
    """Review-scoped trace read port (returns redacted stages only)."""

    async def list_stages(self, actor: ActorContext, enquiry_id: UUID) -> TraceView: ...


async def list_stages(
    actor: ActorContext,
    enquiry_id: UUID,
    *,
    container: AppContainer,
    source: TraceSource | None = None,
) -> TraceView:
    """Return the redacted per-stage trace for an enquiry's current revision (review access)."""
    require_staff_role(actor)
    source = source or require_store(container, "staff_review")
    return await source.list_stages(actor, enquiry_id)
