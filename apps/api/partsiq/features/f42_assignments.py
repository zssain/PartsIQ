"""F42 Assignments facade (helper ``review.assign``).

An admin assigns an active reviewer to an enquiry (or unassigns). The change is applied atomically
with an assignment-history row so access changes IMMEDIATELY: the previous reviewer's next request
fails the assigned-only check and the new reviewer's succeeds. Only an ``admin`` may assign
(a reviewer may not); the assignee must be an active reviewer (a disabled or non-reviewer target
is rejected). The enquiry is locked and the ``expected_revision`` compared (assignment itself does
not bump the compatibility revision); the write is idempotent on the request ``Idempotency-Key``.
Demo review is unaffected — it stays session-scoped and never uses assignment.

Access is ``admin``: the role gate refuses a reviewer-only or non-staff caller with FORBIDDEN (403)
before any enquiry is loaded. Thin adapter over the injected :class:`StaffReviewSource`; the live
locked DB transaction is BLOCKED here.
"""
from __future__ import annotations

from uuid import UUID

from partsiq.core.api_models import AssignmentView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.features.f36_staff_inbox import (
    StaffReviewSource,
    require_staff_review,
    require_staff_role,
)


async def assign(
    actor: ActorContext,
    enquiry_id: UUID,
    assignee_id: UUID | None,
    expected_revision: int,
    key: UUID,
    *,
    container: AppContainer,
    source: StaffReviewSource | None = None,
) -> AssignmentView:
    """Assign or unassign a reviewer (admin-only); access changes immediately once persisted."""
    require_staff_role(actor, admin_only=True)
    source = source or require_staff_review(container)
    return await source.assign(actor, enquiry_id, assignee_id, expected_revision, key)
