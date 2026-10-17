"""Approve / reject a reviewed draft in ONE locked transaction (prompt 14 — F39, F40, F47, F49).

Ported from ``services/orchestrator/app/approval.py`` and adapted to the single ``partsiq``
package: the facts hash now comes from :mod:`partsiq.enquiries.facts` (``facts_sha256``),
verification from :mod:`partsiq.enquiries.verification`, rendering from
:mod:`partsiq.enquiries.renderer`, and the slot content guard from :mod:`partsiq.ai.reply`.

Contracts::

    async def approve(actor, request, key, *, repo) -> ApprovalResult
    async def reject(actor, request, key, *, repo) -> ReviewResult

The decision logic lives here; the single locked transaction (SELECT ... FOR UPDATE, the
atomic decision + approved-part rows + one recommendation message + audit insert, and the
append-only / immutable / one-publication-per-revision indices) lives behind the injected
:class:`ReviewRepository` port so it is testable offline — the live Postgres adapter is
integration work (CONSTRAINTS: live DB is BLOCKED here). Invariants enforced in code,
independent of any model:

  * approve ONLY a verified, current draft bound to its revision and verified fact hash
    (F39/F40). The draft id must match the current draft; the stored verification must have
    passed AND the stored fact hash must equal the current facts hash. Stock is then
    refreshed and the plan re-verified inside the lock, so a changed plan is BLOCKED (F35).
  * a double-click (same idempotency key + the SAME request) publishes EXACTLY once (F39);
    reusing a key with a DIFFERENT payload is an ``IDEMPOTENCY_MISMATCH`` (409).
  * a stale ``expected_revision`` cannot authorize publication — a concurrent correction
    wins (F40) — and the status must be ``awaiting_review``.
  * only this path publishes a recommendation, which the DB couples to its approved decision
    and a one-per-revision unique index (F47); the audit append happens in the same
    transaction so its failure rolls the approval back (F49).
  * ``reject`` records a reason but NEVER publishes a recommendation.

Access is assigned-reviewer (real) or own active demo session (demo); anything else is a 404
so a forged role or a foreign enquiry reveals nothing (F03/F37/F54).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from partsiq.ai.reply import validate_slots
from partsiq.core.contracts import (
    ActorContext,
    ApprovalRequest,
    ApprovalResult,
    Locale,
    RejectionRequest,
    ReviewResult,
    VerifiedFacts,
)
from partsiq.core.errors import PartsIQError

from .facts import facts_sha256
from .renderer import render_reply
from .verification import verify_facts

# The one status from which an approval or rejection may be taken (WORKFLOW: review step).
AWAITING_REVIEW = "awaiting_review"


@dataclass(frozen=True, slots=True)
class ReviewSnapshot:
    """The locked, current review state the decision is checked against.

    Loaded under ``SELECT ... FOR UPDATE`` by the repository; the decision functions here
    never touch a database directly, so the logic stays unit-testable against a fake.
    """

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
    """A previously committed decision, keyed by its idempotency key, for replay."""

    request_hash: str
    approval: ApprovalResult | None = None
    review: ReviewResult | None = None


class ReviewRepository(Protocol):
    """Port over the one locked review transaction.

    The live adapter mirrors the DB invariants the tests fake: the single-publication
    unique index (one recommendation per ``(enquiry_id, revision)``), the idempotency
    unique index (one decision per key), the append-only audit coupled in the same
    transaction, and application-role rejection of UPDATE/DELETE on history.
    """

    async def load_for_review(self, enquiry_id: UUID) -> ReviewSnapshot | None: ...

    async def find_decision_by_key(
        self, enquiry_id: UUID, key: UUID
    ) -> StoredDecision | None: ...

    async def refresh_evidence(self, snapshot: ReviewSnapshot): ...  # -> VerificationEvidence

    async def commit_approval(
        self,
        actor: ActorContext,
        snapshot: ReviewSnapshot,
        request: ApprovalRequest,
        key: UUID,
        rendered_text: str,
    ) -> ApprovalResult: ...

    async def commit_rejection(
        self,
        actor: ActorContext,
        snapshot: ReviewSnapshot,
        request: RejectionRequest,
        key: UUID,
    ) -> ReviewResult: ...


def _canonical_hash(payload: dict) -> str:
    """Stable SHA-256 of a JSON-mode request dump, for idempotency-payload comparison."""
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def authorize_review(actor: ActorContext, snapshot: ReviewSnapshot) -> None:
    """Assigned reviewer (real) or own active demo session (demo); else 404 (reveal nothing).

    Mirrors :func:`partsiq.auth.access.require_access`: a demo enquiry needs the same active
    session and generation; a real enquiry needs a DB-sourced assignment to this reviewer —
    a forged ``roles`` claim alone is never enough. A foreign/unassigned actor gets
    NOT_FOUND (404), never FORBIDDEN, so existence is not leaked.
    """
    if snapshot.session_id is not None:
        same_session = actor.session_id == snapshot.session_id
        same_generation = actor.session_generation == snapshot.session_generation
        if not (same_session and same_generation):
            raise PartsIQError(
                "NOT_FOUND", internal_detail="demo review requires the own active session"
            )
        return
    # Real enquiry: a DB-sourced assignment is required — a forged role claim is not enough.
    if snapshot.assigned_to is None or snapshot.assigned_to != actor.user_id:
        raise PartsIQError(
            "NOT_FOUND", internal_detail="real review requires an assignment to this reviewer"
        )


async def approve(
    actor: ActorContext, request: ApprovalRequest, key: UUID, *, repo: ReviewRepository
) -> ApprovalResult:
    """Publish the single recommendation for the current, verified draft — once.

    The checks run in order: idempotent replay, scope, current revision + status, draft-id
    match, fact-hash binding, re-verification after a stock refresh, then the slot guard for
    any staff edit. Only after all of them does the repository commit the decision, the one
    recommendation message and the audit row in a single transaction.
    """
    request_hash = _canonical_hash(request.model_dump(mode="json"))

    # Idempotent replay: a double-click with the SAME key+payload returns the one result;
    # the same key with a DIFFERENT payload is a mismatch (409) — never a second publish.
    existing = await repo.find_decision_by_key(request.enquiry_id, key)
    if existing is not None:
        if existing.request_hash != request_hash or existing.approval is None:
            raise PartsIQError(
                "IDEMPOTENCY_MISMATCH",
                internal_detail="key reused with a different approval request",
            )
        return existing.approval.model_copy(update={"already_applied": True})

    snapshot = await repo.load_for_review(request.enquiry_id)
    if snapshot is None:
        raise PartsIQError("NOT_FOUND", internal_detail="enquiry not found")
    authorize_review(actor, snapshot)

    if request.expected_revision != snapshot.revision:
        raise PartsIQError(
            "STALE_REVISION",
            internal_detail="a newer revision exists; re-review the current draft",
        )
    if snapshot.status != AWAITING_REVIEW:
        raise PartsIQError(
            "CONFLICT",
            internal_detail=f"enquiry is {snapshot.status!r}, not awaiting review",
        )
    if snapshot.draft_id is None or request.draft_id != snapshot.draft_id:
        raise PartsIQError(
            "CONFLICT", internal_detail="draft id does not match the current draft"
        )

    # F40: approval is bound to the revision AND the verified fact hash. If the stored
    # verification did not pass, or its hash no longer matches the current facts, the plan
    # changed under the reviewer — do not publish.
    if not snapshot.verification_passed or snapshot.facts_sha256 != facts_sha256(snapshot.facts):
        raise PartsIQError(
            "CONFLICT", internal_detail="verified fact hash does not match the current facts"
        )

    # F35: refresh CURRENT stock and re-verify inside the lock. A stale/future snapshot or a
    # quantity that can no longer be allocated makes re-verification fail here, so stale stock
    # never becomes a published (and never a guaranteed) plan. The live search call is wired
    # by the owner; offline it is a deterministic fake.
    evidence = await repo.refresh_evidence(snapshot)
    result = verify_facts(snapshot.facts, evidence)
    if not result.passed:
        raise PartsIQError(
            "CONFLICT", internal_detail="re-verification failed; publication blocked"
        )

    # Staff prose edits use the SAME controlled slot schema and gate; re-render in code so the
    # published message carries code-owned facts, never model- or staff-authored numbers.
    if request.edited_slots is not None:
        validate_slots(request.edited_slots)
        rendered = render_reply(request.edited_slots, snapshot.facts, snapshot.locale)
    else:
        rendered = snapshot.rendered_text

    return await repo.commit_approval(actor, snapshot, request, key, rendered)


async def reject(
    actor: ActorContext, request: RejectionRequest, key: UUID, *, repo: ReviewRepository
) -> ReviewResult:
    """Record a rejection with its reason in one transaction; never publish a recommendation."""
    request_hash = _canonical_hash(request.model_dump(mode="json"))

    existing = await repo.find_decision_by_key(request.enquiry_id, key)
    if existing is not None:
        if existing.request_hash != request_hash or existing.review is None:
            raise PartsIQError(
                "IDEMPOTENCY_MISMATCH",
                internal_detail="key reused with a different rejection request",
            )
        return existing.review

    snapshot = await repo.load_for_review(request.enquiry_id)
    if snapshot is None:
        raise PartsIQError("NOT_FOUND", internal_detail="enquiry not found")
    authorize_review(actor, snapshot)

    if request.expected_revision != snapshot.revision:
        raise PartsIQError(
            "STALE_REVISION",
            internal_detail="a newer revision exists; re-review the current draft",
        )
    if snapshot.status != AWAITING_REVIEW:
        raise PartsIQError(
            "CONFLICT",
            internal_detail=f"enquiry is {snapshot.status!r}, not awaiting review",
        )

    return await repo.commit_rejection(actor, snapshot, request, key)
