"""F40 Approval invalidation facade (helper ``approval.read_binding``).

Reads the current approval BINDING for an enquiry: whether an approval exists, which decision and
fact hash it is bound to, and — crucially — whether it has been INVALIDATED. An approval is bound
to a specific verified fact hash at a specific revision; any later correction (F38) opens a new
revision and invalidates the prior approval, so a stale approval can never publish. This read lets
the workspace show "this approval no longer applies — re-review the current revision". It is
read-only: it publishes nothing and mutates nothing. Access is ``review``; a foreign/unassigned
actor gets NOT_FOUND (404) and a non-staff (demo) caller is refused by the role gate first.

Thin adapter over an injected port; the live DB read is BLOCKED offline, so a reviewer gets a
clean 503 rather than a fabricated binding.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from partsiq.core.api_models import ApprovalState
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.features._ops_ports import require_store
from partsiq.features.f36_staff_inbox import require_staff_role


@runtime_checkable
class ApprovalBindingSource(Protocol):
    """Review-scoped approval-binding read port."""

    async def read_binding(self, actor: ActorContext, enquiry_id: UUID) -> ApprovalState: ...


async def read_binding(
    actor: ActorContext,
    enquiry_id: UUID,
    *,
    container: AppContainer,
    source: ApprovalBindingSource | None = None,
) -> ApprovalState:
    """Return the current approval binding and whether it has been invalidated (review access)."""
    require_staff_role(actor)
    source = source or require_store(container, "staff_review")
    return await source.read_binding(actor, enquiry_id)
