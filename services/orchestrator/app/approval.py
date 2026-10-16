"""Approval and rejection (prompt 14 — F39, F40, F47, F49).

Contracts:
    async def approve(actor: ActorContext, request: ApprovalRequest, key: UUID) -> ApprovalResult
    async def reject(actor: ActorContext, request: RejectionRequest, key: UUID) -> ReviewResult

The decision logic lives here; the locked single transaction (SELECT ... FOR UPDATE, the
atomic decision + approved-parts + one recommendation message + audit insert, and the
append-only/immutable triggers) lives behind the injected ``ReviewRepository`` port so it
is testable offline — the live Postgres adapter is integration work. Invariants enforced
here, independent of the model:
  * approve only a verified, current draft bound to its revision and verified fact hash
    (F39/F40); stock is refreshed and the plan re-verified, so a changed plan is rejected;
  * a double-click (same idempotency key + same request) publishes exactly once (F39);
  * a stale ``expected_revision`` cannot authorize publication (concurrent edit wins, F40);
  * only this path publishes a recommendation, which the DB couples to its approved
    decision and a one-per-revision unique index (F47);
  * rejection records a reason but never publishes a recommendation.
Access is assigned-reviewer (real) or own active demo session (demo); anything else is a
404 so a forged role or a foreign enquiry reveals nothing (F03/F37).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.rendering import render_reply
from app.specialists.reply import validate_slots
from app.verification import canonical_facts_sha256, verify_facts
from partsiq_common.contracts import (
    ActorContext,
    ApprovalRequest,
    ApprovalResult,
    Locale,
    RejectionRequest,
    ReviewResult,
    VerifiedFacts,
)
from partsiq_common.errors import PartsIQError


@dataclass(frozen=True, slots=True)
class ReviewSnapshot:
    """The locked, current review state the decision is checked against."""

    enquiry_id: UUID
    revision: int
    catalogue_version_id: UUID
    status: str
    draft_id: UUID | None
    facts: VerifiedFacts
    verification_id: UUID
    verification_passed: bool
    facts_sha256: str
    locale: Locale
    rendered_text: str = ""
    assigned_to: UUID | None = None
    owner_id: UUID | None = None
    session_id: UUID | None = None
    session_generation: int | None = None


@dataclass(frozen=True, slots=True)
class StoredDecision:
    """A previously committed decision, for idempotent replay."""

    request_hash: str
    approval: ApprovalResult | None = None
    review: ReviewResult | None = None


class ReviewRepository(Protocol):
    async def load_for_review(self, enquiry_id: UUID) -> ReviewSnapshot | None: ...

    async def find_decision_by_key(self, enquiry_id: UUID, key: UUID) -> StoredDecision | None: ...

    async def refresh_evidence(self, snapshot: ReviewSnapshot): ...  # -> VerificationEvidence

    async def commit_approval(
        self, actor: ActorContext, snapshot: ReviewSnapshot, request: ApprovalRequest, key: UUID, rendered_text: str
    ) -> ApprovalResult: ...

    async def commit_rejection(
        self, actor: ActorContext, snapshot: ReviewSnapshot, request: RejectionRequest, key: UUID
    ) -> ReviewResult: ...


def _canonical_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def authorize_review(actor: ActorContext, snapshot: ReviewSnapshot) -> None:
    """Assigned reviewer (real) or own active demo session (demo); else 404 (reveal nothing)."""
    if snapshot.session_id is not None:
        same_session = actor.session_id == snapshot.session_id
        same_generation = actor.session_generation == snapshot.session_generation
        if not (same_session and same_generation):
            raise PartsIQError("NOT_FOUND", internal_detail="demo review requires the own active session")
        return
    # Real enquiry: a DB-sourced assignment is required — a forged role claim is not enough.
    if snapshot.assigned_to is None or snapshot.assigned_to != actor.user_id:
        raise PartsIQError("NOT_FOUND", internal_detail="real review requires an assignment to this reviewer")


async def approve(actor: ActorContext, request: ApprovalRequest, key: UUID, *, repo: ReviewRepository) -> ApprovalResult:
    request_hash = _canonical_hash(request.model_dump(mode="json"))

    existing = await repo.find_decision_by_key(request.enquiry_id, key)
    if existing is not None:
        if existing.request_hash != request_hash or existing.approval is None:
            raise PartsIQError("IDEMPOTENCY_MISMATCH", internal_detail="key reused with a different approval request")
        return existing.approval.model_copy(update={"already_applied": True})  # double-click publishes once

    snapshot = await repo.load_for_review(request.enquiry_id)
    if snapshot is None:
        raise PartsIQError("NOT_FOUND", internal_detail="enquiry not found")
    authorize_review(actor, snapshot)

    if request.expected_revision != snapshot.revision:
        raise PartsIQError("STALE_REVISION", internal_detail="a newer revision exists; re-review the current draft")
    if snapshot.draft_id is None or request.draft_id != snapshot.draft_id:
        raise PartsIQError("CONFLICT", internal_detail="draft id does not match the current draft")

    # F40: approval is bound to the revision AND the verified fact hash. If the stored
    # verification does not match the current facts, the plan changed — do not publish.
    if not snapshot.verification_passed or snapshot.facts_sha256 != canonical_facts_sha256(snapshot.facts):
        raise PartsIQError("CONFLICT", internal_detail="verified fact hash does not match the current facts")

    # Refresh stock through search and re-verify; a changed plan fails publication.
    evidence = await repo.refresh_evidence(snapshot)
    result = verify_facts(snapshot.facts, evidence)
    if not result.passed:
        raise PartsIQError("CONFLICT", internal_detail="re-verification failed; publication blocked")

    # Staff prose edits use the SAME controlled slot schema; re-render in code.
    if request.edited_slots is not None:
        validate_slots(request.edited_slots)
        rendered = render_reply(request.edited_slots, snapshot.facts, snapshot.locale)
    else:
        rendered = snapshot.rendered_text

    return await repo.commit_approval(actor, snapshot, request, key, rendered)


async def reject(actor: ActorContext, request: RejectionRequest, key: UUID, *, repo: ReviewRepository) -> ReviewResult:
    """Record a rejection with its reason in one transaction; never publish a recommendation."""
    request_hash = _canonical_hash(request.model_dump(mode="json"))

    existing = await repo.find_decision_by_key(request.enquiry_id, key)
    if existing is not None:
        if existing.request_hash != request_hash or existing.review is None:
            raise PartsIQError("IDEMPOTENCY_MISMATCH", internal_detail="key reused with a different rejection request")
        return existing.review

    snapshot = await repo.load_for_review(request.enquiry_id)
    if snapshot is None:
        raise PartsIQError("NOT_FOUND", internal_detail="enquiry not found")
    authorize_review(actor, snapshot)

    if request.expected_revision != snapshot.revision:
        raise PartsIQError("STALE_REVISION", internal_detail="a newer revision exists; re-review the current draft")

    return await repo.commit_rejection(actor, snapshot, request, key)
