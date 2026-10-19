"""F39 Review actions facade (helpers ``approval.approve`` / ``approval.reject``).

The human publication gate. ``approve`` publishes EXACTLY ONE recommendation for the current,
verified draft — and only when verification passed, the draft id matches the current draft, the
revision is current and the verified fact hash still matches the plan
(:func:`partsiq.enquiries.approval.approve`); a double-click with the same idempotency key + the
same payload publishes once, a different payload is a 409. ``reject`` records a reason and NEVER
publishes a recommendation. Access is ``review`` (assigned reviewer or own active demo session);
a foreign/unassigned actor gets NOT_FOUND (404). No LLM authorizes either decision.

Thin adapter over the injected :class:`StaffReviewSource`; the live locked DB transaction is
BLOCKED here. The ``Idempotency-Key`` required by every mutating request is passed through so the
single-publication / idempotent-replay invariants are enforced at the committing boundary.
"""
from __future__ import annotations

from uuid import UUID

from partsiq.core.contracts import (
    ActorContext,
    ApprovalRequest,
    ApprovalResult,
    RejectionRequest,
    ReviewResult,
)
from partsiq.core.dependencies import AppContainer
from partsiq.features.f36_staff_inbox import (
    StaffReviewSource,
    resolve_review_source,
)


async def approve(
    actor: ActorContext,
    request: ApprovalRequest,
    key: UUID,
    *,
    container: AppContainer,
    source: StaffReviewSource | None = None,
) -> ApprovalResult:
    """Publish the single recommendation for the current, verified draft — once (review access).

    ``review`` access = assigned reviewer / admin / own active demo session. In fixture mode the
    own-session journey publishes it idempotently (F03); real enquiries use the locked DB path.
    """
    source = resolve_review_source(container, actor, source=source)
    return await source.approve(actor, request, key)


async def reject(
    actor: ActorContext,
    request: RejectionRequest,
    key: UUID,
    *,
    container: AppContainer,
    source: StaffReviewSource | None = None,
) -> ReviewResult:
    """Record a rejection with its reason; never publishes a recommendation (review access)."""
    source = resolve_review_source(container, actor, source=source)
    return await source.reject(actor, request, key)
