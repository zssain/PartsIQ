"""F46 Verification gate facade (helper ``verification.read_current``).

Reads the CURRENT verification result for an enquiry's draft: whether every claimed fact
(compatibility, part identity, stock) is backed by evidence, the list of any failures, and the
fact hash the result is bound to. Approval (F39) is gated on this passing, so the workspace reads
it to enable or block the approve action. It is read-only and derived from the committed verified
facts — it never re-derives a fact with an LLM and never fabricates a pass. Access is ``review``;
a foreign/unassigned actor gets NOT_FOUND (404) and a non-staff (demo) caller is refused first.

Thin adapter over an injected port; the live DB read is BLOCKED offline, so a reviewer gets a
clean 503 rather than a fabricated verification.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from partsiq.core.contracts import ActorContext, VerificationResult
from partsiq.core.dependencies import AppContainer
from partsiq.features._ops_ports import require_store
from partsiq.features.f36_staff_inbox import require_staff_role


@runtime_checkable
class VerificationSource(Protocol):
    """Review-scoped verification read port."""

    async def read_verification(
        self, actor: ActorContext, enquiry_id: UUID
    ) -> VerificationResult: ...


async def read_current(
    actor: ActorContext,
    enquiry_id: UUID,
    *,
    container: AppContainer,
    source: VerificationSource | None = None,
) -> VerificationResult:
    """Return the current verification result gating approval for this enquiry (review access)."""
    require_staff_role(actor)
    source = source or require_store(container, "staff_review")
    return await source.read_verification(actor, enquiry_id)
