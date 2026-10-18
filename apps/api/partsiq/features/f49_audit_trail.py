"""F49 Audit trail facade (helper ``audit.list_events``).

Exposes the append-only audit events persisted by the review/approval path
(:mod:`partsiq.enquiries.publication` appends one MINIMAL, redacted :class:`AuditEvent` in the
same transaction as every irreversible decision). This is a READ surface: it never writes, and the
events are returned in stable append order (oldest-first), keyset-paged. Each event carries
who/what/which-revision and the fact hash only — never reply prose, citation text or any secret
(F49). Access is ``review`` (assigned reviewer / own active demo session); a foreign/unassigned
actor gets NOT_FOUND (404) before any event is read.

Thin adapter over the injected :class:`StaffReviewSource`; the live append-only DB adapter (which
rejects UPDATE/DELETE on the audit table) is BLOCKED here.
"""
from __future__ import annotations

from uuid import UUID

from partsiq.core.api_models import AuditPage, PageQuery
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.features.f36_staff_inbox import (
    StaffReviewSource,
    require_staff_review,
    require_staff_role,
)


async def list_events(
    actor: ActorContext,
    enquiry_id: UUID,
    query: PageQuery,
    *,
    container: AppContainer,
    source: StaffReviewSource | None = None,
) -> AuditPage:
    """List an enquiry's append-only audit events in stable order (review access; 404 foreign)."""
    require_staff_role(actor)
    source = source or require_staff_review(container)
    return await source.list_audit(actor, enquiry_id, query)
