"""Assemble the current review snapshot for an authorized reviewer (prompt 14 — F37).

Contract: ``async def load_review_view(actor, enquiry_id, *, repo) -> ReviewView``.

A :class:`~partsiq.core.api_models.ReviewView` is the read model the review workspace needs:
the current :class:`EnquiryView`, the verified :class:`VerifiedFacts`, the reply
:class:`ReplySlots` draft, the :class:`VerificationResult`, and the ``assigned_to`` reviewer.
It is read-only: assembling it publishes nothing and mutates nothing.

Access is the SAME rule the write path enforces (:func:`partsiq.enquiries.approval.authorize_review`):
the assigned reviewer of a real enquiry, or the owner of the matching active demo session.
A foreign or unassigned actor gets NOT_FOUND (404), never a 403 — existence is not leaked
(F37: "unassigned reviewer receives 404"). Missing panels are returned as ``None`` so the
workspace can render explicit empty states (F37: "missing panels show explicit empty states")
rather than fabricating facts.

The read is performed through an injected :class:`ReviewReadRepository` port so this module is
testable offline; the live Postgres adapter is wired by the owner (live DB is BLOCKED here).
"""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from partsiq.core.api_models import ReviewView
from partsiq.core.contracts import (
    ActorContext,
    EnquiryView,
    ReplySlots,
    VerificationResult,
    VerifiedFacts,
)
from partsiq.core.errors import PartsIQError

from .approval import ReviewSnapshot, authorize_review


class ReviewReadRepository(Protocol):
    """Read port: the locked snapshot (for scope) plus the assembled view parts.

    ``load_for_review`` is shared with the write path so the SAME authorization facts
    (assignment / demo session) gate the read; ``load_view_parts`` returns the four optional
    panels. Any panel may be ``None`` — a draft not yet rendered, facts not yet planned —
    which the view surfaces as an explicit empty state.
    """

    async def load_for_review(self, enquiry_id: UUID) -> ReviewSnapshot | None: ...

    async def load_view_parts(
        self, enquiry_id: UUID
    ) -> tuple[
        EnquiryView,
        VerifiedFacts | None,
        ReplySlots | None,
        VerificationResult | None,
    ]: ...


async def load_review_view(
    actor: ActorContext, enquiry_id: UUID, *, repo: ReviewReadRepository
) -> ReviewView:
    """Return the current :class:`ReviewView` for an authorized reviewer, or raise 404.

    The snapshot is loaded first so scope is checked exactly as the approve/reject path
    checks it; an unauthorized actor is rejected before any view part is assembled, so an
    unassigned reviewer learns nothing about the enquiry.
    """
    snapshot = await repo.load_for_review(enquiry_id)
    if snapshot is None:
        raise PartsIQError("NOT_FOUND", internal_detail="enquiry not found")
    authorize_review(actor, snapshot)

    enquiry, facts, draft, verification = await repo.load_view_parts(enquiry_id)
    return ReviewView(
        enquiry=enquiry,
        facts=facts,
        draft=draft,
        verification=verification,
        assigned_to=snapshot.assigned_to,
    )
