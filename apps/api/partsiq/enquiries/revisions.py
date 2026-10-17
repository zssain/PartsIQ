"""Enquiry corrections: increment the revision, snapshot immutably (prompt 14 — F38, F40).

Ported from ``services/orchestrator/app/revisions.py`` and adapted to the single ``partsiq``
package. Contract: ``async def revise(actor, request, *, repo) -> EnquiryView``.

A correction LOCKS the enquiry, re-authorizes the actor (owner, assigned reviewer, or own
active demo session) and compares the expected revision BEFORE anything changes — a stale
correction is rejected with STALE_REVISION (F38: "old revision returns 409"). It then
increments the revision and appends an IMMUTABLE revision snapshot, recording the before/after
of every corrected field and invalidating the derived selection, plan, draft and approval so
recomputation re-runs for the new revision.

A historical approval is NEVER mutated (F40: "an old approval cannot authorize a new
revision"): the prior revision's approved decision and its immutable snapshot stay exactly as
they were; the new revision simply has no approval until it is re-reviewed. The correction
cannot directly set an approved status or invent candidate facts — it only edits the typed
allowed fields.

The locked transaction + append-only revision-snapshot trigger live behind the injected
:class:`RevisionRepository` port so the logic is testable offline; the live Postgres adapter
(the immutable ``enquiry_revisions`` history and application-role UPDATE/DELETE rejection on
it) is wired by the owner (live DB is BLOCKED here).
"""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from partsiq.core.contracts import ActorContext, EnquiryView, RevisionRequest
from partsiq.core.errors import PartsIQError

from .approval import ReviewSnapshot


class RevisionRepository(Protocol):
    """Port over the one locked correction transaction.

    ``apply_revision`` increments the revision, appends the immutable snapshot, records the
    before/after values and resets derived state — all atomically. The live adapter's
    append-only history rejects any attempt to mutate a prior approval or snapshot.
    """

    async def load_for_review(self, enquiry_id: UUID) -> ReviewSnapshot | None: ...

    async def apply_revision(
        self, actor: ActorContext, snapshot: ReviewSnapshot, request: RevisionRequest
    ) -> EnquiryView: ...


def authorize_revision(actor: ActorContext, snapshot: ReviewSnapshot) -> None:
    """Owner, assigned reviewer, or own active demo session may correct; else 404.

    A demo correction needs the same active session and generation; a real correction needs
    ownership or an assignment to this actor. Anything else is NOT_FOUND so a foreign or
    stale-session actor learns nothing.
    """
    if snapshot.session_id is not None:
        if (
            actor.session_id == snapshot.session_id
            and actor.session_generation == snapshot.session_generation
        ):
            return
        raise PartsIQError(
            "NOT_FOUND", internal_detail="demo correction requires the own active session"
        )
    if actor.user_id is not None and actor.user_id in (snapshot.owner_id, snapshot.assigned_to):
        return
    raise PartsIQError(
        "NOT_FOUND", internal_detail="correction requires ownership or assignment"
    )


async def revise(
    actor: ActorContext, request: RevisionRequest, *, repo: RevisionRepository
) -> EnquiryView:
    """Apply a correction: lock, re-authorize, check revision, then increment + snapshot.

    The port increments the revision, appends the immutable snapshot and resets status to
    processing for recomputation; historical approvals are never mutated (F40).
    """
    snapshot = await repo.load_for_review(request.enquiry_id)
    if snapshot is None:
        raise PartsIQError("NOT_FOUND", internal_detail="enquiry not found")
    authorize_revision(actor, snapshot)

    if request.expected_revision != snapshot.revision:
        raise PartsIQError(
            "STALE_REVISION",
            internal_detail="a newer revision exists; reload before correcting",
        )

    return await repo.apply_revision(actor, snapshot, request)
