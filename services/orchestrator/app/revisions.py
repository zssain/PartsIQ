"""Enquiry revisions / corrections (prompt 14 — F38, F40).

Contract: ``async def revise(actor: ActorContext, request: RevisionRequest) -> EnquiryView``.

A correction increments the revision and appends an immutable revision snapshot; it never
updates a historical approval (F40: an old approval cannot authorize a new revision). The
enquiry is locked and the actor re-authorized (owner, assigned reviewer, or own active demo
session) and the expected revision compared before anything changes — a stale correction is
rejected. The locked transaction + immutable-snapshot trigger live behind the injected port
so the logic is testable offline; the live Postgres adapter is integration work.
"""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.approval import ReviewSnapshot
from partsiq_common.contracts import ActorContext, EnquiryView, RevisionRequest
from partsiq_common.errors import PartsIQError


class RevisionRepository(Protocol):
    async def load_for_review(self, enquiry_id: UUID) -> ReviewSnapshot | None: ...

    async def apply_revision(
        self, actor: ActorContext, snapshot: ReviewSnapshot, request: RevisionRequest
    ) -> EnquiryView: ...


def authorize_revision(actor: ActorContext, snapshot: ReviewSnapshot) -> None:
    """Owner, assigned reviewer, or own active demo session may correct; else 404."""
    if snapshot.session_id is not None:
        if actor.session_id == snapshot.session_id and actor.session_generation == snapshot.session_generation:
            return
        raise PartsIQError("NOT_FOUND", internal_detail="demo correction requires the own active session")
    if actor.user_id in (snapshot.owner_id, snapshot.assigned_to) and actor.user_id is not None:
        return
    raise PartsIQError("NOT_FOUND", internal_detail="correction requires ownership or assignment")


async def revise(actor: ActorContext, request: RevisionRequest, *, repo: RevisionRepository) -> EnquiryView:
    snapshot = await repo.load_for_review(request.enquiry_id)
    if snapshot is None:
        raise PartsIQError("NOT_FOUND", internal_detail="enquiry not found")
    authorize_revision(actor, snapshot)

    if request.expected_revision != snapshot.revision:
        raise PartsIQError("STALE_REVISION", internal_detail="a newer revision exists; reload before correcting")

    # The port increments the revision, appends the immutable snapshot and sets status
    # back to processing; historical approvals are never mutated (F40).
    return await repo.apply_revision(actor, snapshot, request)
