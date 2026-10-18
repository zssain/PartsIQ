"""F50 Durable workflows facade (helper ``workflow.inspect_run``).

Returns the durable workflow state for an enquiry: the current step, the steps already completed,
any pending background job id, and an error code if the run is parked. The workflow is the single
source of truth for "what happens next" — it is durable (survives a restart) and advances only
through committed transitions, so this read lets the workspace show progress without re-deriving
state. It is read-only and never advances the run. Access is ``review``; a foreign/unassigned
actor gets NOT_FOUND (404) and a non-staff (demo) caller is refused by the role gate first.

Thin adapter over an injected port; the live workflow store is BLOCKED offline, so a reviewer gets
a clean 503 rather than a fabricated run state.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from partsiq.core.api_models import WorkflowView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.features._ops_ports import require_store
from partsiq.features.f36_staff_inbox import require_staff_role


@runtime_checkable
class WorkflowSource(Protocol):
    """Review-scoped durable-workflow read port."""

    async def inspect_run(self, actor: ActorContext, enquiry_id: UUID) -> WorkflowView: ...


async def inspect_run(
    actor: ActorContext,
    enquiry_id: UUID,
    *,
    container: AppContainer,
    source: WorkflowSource | None = None,
) -> WorkflowView:
    """Return the durable workflow state for an enquiry (review access; read-only)."""
    require_staff_role(actor)
    source = source or require_store(container, "workflow_runs")
    return await source.inspect_run(actor, enquiry_id)
