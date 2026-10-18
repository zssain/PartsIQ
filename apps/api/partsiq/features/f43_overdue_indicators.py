"""F43 Overdue indicators facade (helper ``review.deadline``).

Returns the review deadline for an enquiry and whether it is overdue. The deadline is the
enquiry's ``created_at`` plus a configurable urgent/normal threshold; overdue is flagged ONLY for
unresolved states — an approved/rejected/failed enquiry is never overdue. Every instant is UTC so
a daylight-saving display change can never move the deadline. These thresholds are an internal
triage aid, NOT a contractual SLA. Access is ``review`` (assigned reviewer / own active demo
session); a foreign/unassigned actor gets NOT_FOUND (404).

The clock and the deadline computation live in the store so ``server_time`` is a single trusted
source; this is a thin adapter over the injected :class:`StaffReviewSource`. The live DB adapter
is BLOCKED here.
"""
from __future__ import annotations

from uuid import UUID

from partsiq.core.api_models import DeadlineView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.features.f36_staff_inbox import (
    StaffReviewSource,
    require_staff_review,
    require_staff_role,
)


async def deadline(
    actor: ActorContext,
    enquiry_id: UUID,
    *,
    container: AppContainer,
    source: StaffReviewSource | None = None,
) -> DeadlineView:
    """Return the UTC due_at, server_time and overdue flag for an enquiry (review access)."""
    require_staff_role(actor)
    source = source or require_staff_review(container)
    return await source.deadline(actor, enquiry_id)
