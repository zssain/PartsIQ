"""F37 Review workspace facade (helper ``review.get_workspace``).

Assembles the current :class:`~partsiq.core.api_models.ReviewView` for an authorized reviewer: the
enquiry, the verified facts, the reply-slots draft, the verification result and the assigned
reviewer. It is read-only — assembling it publishes nothing and mutates nothing. Access is
``review``: the assigned reviewer of a real enquiry or the owner of the matching active demo
session; a foreign/unassigned actor gets NOT_FOUND (404), never a 403 that leaks existence
(mirrors :func:`partsiq.enquiries.review.load_review_view`). Missing panels come back as ``None``
so the workspace renders explicit empty states rather than fabricating facts.

Thin adapter over the injected :class:`StaffReviewSource`; the live DB adapter is BLOCKED here.
"""
from __future__ import annotations

from uuid import UUID

from partsiq.core.api_models import ReviewView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.features.f36_staff_inbox import (
    StaffReviewSource,
    require_staff_review,
    require_staff_role,
)


async def get_workspace(
    actor: ActorContext,
    enquiry_id: UUID,
    *,
    container: AppContainer,
    source: StaffReviewSource | None = None,
) -> ReviewView:
    """Return the current review snapshot for an authorized reviewer (review access; 404 foreign)."""
    require_staff_role(actor)
    source = source or require_staff_review(container)
    return await source.get_workspace(actor, enquiry_id)
