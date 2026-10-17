"""Foundation 14 acceptance: review, approval, revision and publication (F39, F40, F47, F49).

Ports the behaviour characterized in services/orchestrator/tests/features/test_f40.py,
test_f47.py and tests/acceptance/test_f49.py, consolidated onto the single ``partsiq``
package.

Deterministic and fully offline: the live Postgres adapter is BLOCKED. Injected fake
repositories mirror the DB invariants the live adapter enforces:
  * the single-publication UNIQUE index (one recommendation per (enquiry_id, revision));
  * the idempotency UNIQUE index (one decision per key);
  * the recommendation-requires-approved-decision CHECK;
  * the append-only audit in the SAME transaction (its failure rolls the approval back);
  * immutable revision history (a prior approval is never mutated).
The live DB path is SKIPPED, never faked.

Covered behaviours:
  * approve ONLY when verification passed AND status == awaiting_review;
  * a double-click (same idempotency key + payload) publishes exactly once;
  * key reuse with a DIFFERENT payload -> IDEMPOTENCY_MISMATCH;
  * a stale expected_revision -> STALE_REVISION (409);
  * a foreign / unassigned reviewer -> NOT_FOUND (404); forged role is not enough;
  * a changed plan after the stock refresh BLOCKS publication (F35/F40);
  * a drifted verified fact hash blocks publication (F40);
  * staff-edited slots go through validate_slots (digits/identifiers rejected);
  * reject records a reason and publishes nothing;
  * revise increments the revision + snapshots immutably and never mutates a prior
    approval (F40);
  * the audit row is in the same transaction and its failure rolls back (F49), and it is
    minimal/redacted;
  * publish_recommendation couples the message to its approved decision and builds the
    immutable ApprovedSnapshot; the review view is assembled only for an authorized reviewer.
"""
from __future__ import annotations

import os
import unittest
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from partsiq.core.api_models import ReviewView
from partsiq.core.contracts import (
    ActorContext,
    Allocation,
    ApprovalRequest,
    ApprovalResult,
    ApprovedSnapshot,
    AuditEvent,
    CandidateEvidence,
    EnquiryView,
    RejectionRequest,
    ReplySlots,
    ReviewResult,
    RevisionRequest,
    ItemCorrection,
    StockEvidence,
    VerificationEvidence,
    VerificationResult,
    VerifiedFacts,
    VerifiedItem,
)
from partsiq.core.errors import PartsIQError
from partsiq.enquiries.approval import ReviewSnapshot, StoredDecision, approve, reject
from partsiq.enquiries.facts import facts_sha256
from partsiq.enquiries.publication import (
    build_approved_snapshot,
    build_audit_event,
    publish_recommendation,
)
from partsiq.enquiries.renderer import render_reply
from partsiq.enquiries.review import load_review_view
from partsiq.enquiries.revisions import revise

WHEN = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _facts(enquiry_id=None, revision=1, catalogue=None):
    return VerifiedFacts(
        enquiry_id=enquiry_id or uuid4(),
        revision=revision,
        catalogue_version_id=catalogue or uuid4(),
        items=[
            VerifiedItem(
                item_id=uuid4(),
                configuration_id=100,
                part_id=10,
                part_number="VP-FF-10",
                name_en="fuel filter",
                name_ar="فلتر وقود",
                requested_quantity=Decimal("2"),
                allocations=[
                    Allocation(
                        warehouse_id=1,
                        quantity=Decimal("2"),
                        transfer_days=2,
                        stock_updated_at=WHEN,
                    )
                ],
                shortage=Decimal("0"),
                source_reference="SYNTH-CA-PB-CA-110 rev 1, section FILTERS",
                evidence_id=uuid4(),
            )
        ],
    )


def _evidence(facts, *, passes=True):
    """Evidence that re-verifies the facts; ``passes=False`` flips the active catalogue."""
    agg: dict[tuple[int, int], Decimal] = defaultdict(lambda: Decimal("0"))
    candidates = []
    for item in facts.items:
        candidates.append(
            CandidateEvidence(
                item_id=item.item_id,
                part_id=item.part_id,
                configuration_id=item.configuration_id,
                evidence_id=item.evidence_id,
                source_reference=item.source_reference,
            )
        )
        for allocation in item.allocations:
            agg[(item.part_id, allocation.warehouse_id)] += allocation.quantity
    stock = [
        StockEvidence(part_id=p, warehouse_id=w, available=q, updated_at=WHEN)
        for (p, w), q in agg.items()
    ]
    return VerificationEvidence(
        current_revision=facts.revision,
        active_catalogue_version_id=facts.catalogue_version_id if passes else uuid4(),
        candidates=candidates,
        stock=stock,
    )


def _snapshot(
    uid,
    *,
    revision=1,
    status="awaiting_review",
    drift=False,
    draft_id=None,
    facts=None,
    session_id=None,
    session_generation=None,
    assigned_to=None,
    owner_id=None,
):
    facts = facts or _facts(revision=revision)
    return ReviewSnapshot(
        enquiry_id=facts.enquiry_id,
        revision=revision,
        catalogue_version_id=facts.catalogue_version_id,
        status=status,
        draft_id=draft_id or uuid4(),
        facts=facts,
        verification_id=uuid4(),
        verification_passed=True,
        facts_sha256="0" * 64 if drift else facts_sha256(facts),
        locale="en",
        rendered_text="<div>r</div>",
        assigned_to=assigned_to if assigned_to is not None else uid,
        owner_id=owner_id if owner_id is not None else uid,
        session_id=session_id,
        session_generation=session_generation,
    )


def _actor(uid=None, *, roles=("reviewer",), session_id=None, session_generation=None):
    return ActorContext(
        user_id=uid or uuid4(),
        request_id=uuid4(),
        roles=list(roles),
        session_id=session_id,
        session_generation=session_generation,
    )


class ReviewRepo:
    """Fake ReviewRepository mirroring the DB invariants the live adapter enforces."""

    def __init__(self, snapshot, *, passes=True, audit_fails=False):
        self.snapshot = snapshot
        self.passes = passes
        self.audit_fails = audit_fails
        self.by_key: dict[UUID, StoredDecision] = {}
        self.published: dict[int, UUID] = {}  # revision -> message_id (UNIQUE index)
        self.audit: list[dict] = []

    async def load_for_review(self, enquiry_id):
        return self.snapshot if self.snapshot and self.snapshot.enquiry_id == enquiry_id else None

    async def find_decision_by_key(self, enquiry_id, key):
        return self.by_key.get(key)

    async def refresh_evidence(self, snapshot):
        return _evidence(snapshot.facts, passes=self.passes)

    async def commit_approval(self, actor, snapshot, request, key, rendered_text):
        # One recommendation per (enquiry, revision): the UNIQUE index backstop.
        if snapshot.revision in self.published:
            raise PartsIQError(
                "CONFLICT", internal_detail="recommendation already published for this revision"
            )
        decision_id = uuid4()
        # Same-transaction audit append; its failure rolls the whole approval back (F49).
        if self.audit_fails:
            raise PartsIQError(
                "DEPENDENCY_UNAVAILABLE", internal_detail="audit write failed; txn rolled back"
            )
        self.audit.append(
            {
                "actor_id": str(actor.user_id),
                "action": "approve",
                "entity_type": "review_decision",
                "entity_id": str(decision_id),
                "request_id": str(actor.request_id),
                "revision": snapshot.revision,
            }
        )
        message_id = uuid4()
        self.published[snapshot.revision] = message_id
        result = ApprovalResult(
            decision_id=decision_id,
            message_id=message_id,
            revision=snapshot.revision,
            already_applied=False,
        )
        # Record the committed decision for idempotent replay by this key.
        import hashlib
        import json

        request_hash = hashlib.sha256(
            json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        self.by_key[key] = StoredDecision(request_hash=request_hash, approval=result)
        return result

    async def commit_rejection(self, actor, snapshot, request, key):
        decision_id = uuid4()
        self.audit.append(
            {
                "actor_id": str(actor.user_id),
                "action": "reject",
                "entity_id": str(decision_id),
                "reason": request.reason,
                "revision": snapshot.revision,
            }
        )
        result = ReviewResult(decision_id=decision_id, revision=snapshot.revision, status="rejected")
        import hashlib
        import json

        request_hash = hashlib.sha256(
            json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        self.by_key[key] = StoredDecision(request_hash=request_hash, review=result)
        return result


# ---------------------------------------------------------------------------
# approve — happy path + the publication gate.
# ---------------------------------------------------------------------------
class Approve(unittest.IsolatedAsyncioTestCase):
    async def test_approves_current_verified_draft(self):
        uid = uuid4()
        snap = _snapshot(uid)
        repo = ReviewRepo(snap)
        req = ApprovalRequest(enquiry_id=snap.enquiry_id, expected_revision=1, draft_id=snap.draft_id)
        result = await approve(_actor(uid), req, uuid4(), repo=repo)
        self.assertIsNotNone(result.decision_id)
        self.assertIsNotNone(result.message_id)
        self.assertFalse(result.already_applied)
        self.assertEqual(len(repo.published), 1)

    async def test_approve_requires_awaiting_review_status(self):
        uid = uuid4()
        snap = _snapshot(uid, status="processing")
        repo = ReviewRepo(snap)
        req = ApprovalRequest(enquiry_id=snap.enquiry_id, expected_revision=1, draft_id=snap.draft_id)
        with self.assertRaises(PartsIQError) as ctx:
            await approve(_actor(uid), req, uuid4(), repo=repo)
        self.assertEqual(ctx.exception.code, "CONFLICT")
        self.assertEqual(len(repo.published), 0)

    async def test_failed_reverification_blocks_publication(self):
        uid = uuid4()
        snap = _snapshot(uid)
        repo = ReviewRepo(snap, passes=False)  # stock refresh yields a changed plan
        req = ApprovalRequest(enquiry_id=snap.enquiry_id, expected_revision=1, draft_id=snap.draft_id)
        with self.assertRaises(PartsIQError) as ctx:
            await approve(_actor(uid), req, uuid4(), repo=repo)
        self.assertEqual(ctx.exception.code, "CONFLICT")
        self.assertEqual(len(repo.published), 0)

    async def test_changed_plan_after_stock_refresh_blocks(self):
        # F35: a stock quantity that can no longer be allocated fails re-verification.
        uid = uuid4()
        snap = _snapshot(uid)

        class ShortStock(ReviewRepo):
            async def refresh_evidence(self, snapshot):
                ev = _evidence(snapshot.facts)
                shorted = [
                    r.model_copy(update={"available": Decimal("0")}) for r in ev.stock
                ]
                return ev.model_copy(update={"stock": shorted})

        repo = ShortStock(snap)
        req = ApprovalRequest(enquiry_id=snap.enquiry_id, expected_revision=1, draft_id=snap.draft_id)
        with self.assertRaises(PartsIQError) as ctx:
            await approve(_actor(uid), req, uuid4(), repo=repo)
        self.assertEqual(ctx.exception.code, "CONFLICT")
        self.assertEqual(len(repo.published), 0)

    async def test_fact_hash_drift_blocks_publication(self):
        uid = uuid4()
        snap = _snapshot(uid, drift=True)
        repo = ReviewRepo(snap)
        req = ApprovalRequest(enquiry_id=snap.enquiry_id, expected_revision=1, draft_id=snap.draft_id)
        with self.assertRaises(PartsIQError) as ctx:
            await approve(_actor(uid), req, uuid4(), repo=repo)
        self.assertEqual(ctx.exception.code, "CONFLICT")
        self.assertEqual(len(repo.published), 0)

    async def test_wrong_draft_id_blocks(self):
        uid = uuid4()
        snap = _snapshot(uid)
        repo = ReviewRepo(snap)
        req = ApprovalRequest(enquiry_id=snap.enquiry_id, expected_revision=1, draft_id=uuid4())
        with self.assertRaises(PartsIQError) as ctx:
            await approve(_actor(uid), req, uuid4(), repo=repo)
        self.assertEqual(ctx.exception.code, "CONFLICT")
        self.assertEqual(len(repo.published), 0)


# ---------------------------------------------------------------------------
# approve — revision / idempotency / access boundaries.
# ---------------------------------------------------------------------------
class ApproveBoundaries(unittest.IsolatedAsyncioTestCase):
    async def test_stale_expected_revision_409(self):
        uid = uuid4()
        snap = _snapshot(uid, revision=3)
        repo = ReviewRepo(snap)
        req = ApprovalRequest(enquiry_id=snap.enquiry_id, expected_revision=2, draft_id=snap.draft_id)
        with self.assertRaises(PartsIQError) as ctx:
            await approve(_actor(uid), req, uuid4(), repo=repo)
        self.assertEqual(ctx.exception.code, "STALE_REVISION")
        self.assertEqual(len(repo.published), 0)

    async def test_double_click_publishes_once(self):
        uid = uuid4()
        snap = _snapshot(uid)
        repo = ReviewRepo(snap)
        req = ApprovalRequest(enquiry_id=snap.enquiry_id, expected_revision=1, draft_id=snap.draft_id)
        key = uuid4()
        first = await approve(_actor(uid), req, key, repo=repo)
        second = await approve(_actor(uid), req, key, repo=repo)  # same key + payload
        self.assertEqual(first.decision_id, second.decision_id)
        self.assertEqual(first.message_id, second.message_id)
        self.assertFalse(first.already_applied)
        self.assertTrue(second.already_applied)
        self.assertEqual(len(repo.published), 1)  # exactly one recommendation

    async def test_key_reuse_with_different_payload_mismatch(self):
        uid = uuid4()
        snap = _snapshot(uid)
        repo = ReviewRepo(snap)
        key = uuid4()
        await approve(
            _actor(uid),
            ApprovalRequest(enquiry_id=snap.enquiry_id, expected_revision=1, draft_id=snap.draft_id),
            key,
            repo=repo,
        )
        # Same key, different payload (an edited slot changes the request hash).
        edited = ReplySlots(greeting="Hello", explanation="Your selection is ready.", closing="Regards")
        with self.assertRaises(PartsIQError) as ctx:
            await approve(
                _actor(uid),
                ApprovalRequest(
                    enquiry_id=snap.enquiry_id,
                    expected_revision=1,
                    draft_id=snap.draft_id,
                    edited_slots=edited,
                ),
                key,
                repo=repo,
            )
        self.assertEqual(ctx.exception.code, "IDEMPOTENCY_MISMATCH")

    async def test_unassigned_reviewer_404(self):
        # A valid reviewer who is NOT the assigned reviewer gets 404, not 403.
        snap = _snapshot(uuid4())  # assigned to someone else
        repo = ReviewRepo(snap)
        stranger = _actor(uuid4(), roles=("reviewer",))
        req = ApprovalRequest(enquiry_id=snap.enquiry_id, expected_revision=1, draft_id=snap.draft_id)
        with self.assertRaises(PartsIQError) as ctx:
            await approve(stranger, req, uuid4(), repo=repo)
        self.assertEqual(ctx.exception.code, "NOT_FOUND")
        self.assertEqual(len(repo.published), 0)

    async def test_forged_role_without_assignment_404(self):
        # A forged 'admin'/'reviewer' claim grants nothing without a DB-sourced assignment.
        snap = _snapshot(uuid4())
        repo = ReviewRepo(snap)
        forged = _actor(uuid4(), roles=("admin", "reviewer"))
        req = ApprovalRequest(enquiry_id=snap.enquiry_id, expected_revision=1, draft_id=snap.draft_id)
        with self.assertRaises(PartsIQError) as ctx:
            await approve(forged, req, uuid4(), repo=repo)
        self.assertEqual(ctx.exception.code, "NOT_FOUND")

    async def test_foreign_demo_session_404(self):
        session_id = uuid4()
        snap = _snapshot(uuid4(), session_id=session_id, session_generation=1)
        repo = ReviewRepo(snap)
        # Wrong generation (stale/reset session) -> not found.
        actor = _actor(session_id=session_id, session_generation=2)
        req = ApprovalRequest(enquiry_id=snap.enquiry_id, expected_revision=1, draft_id=snap.draft_id)
        with self.assertRaises(PartsIQError) as ctx:
            await approve(actor, req, uuid4(), repo=repo)
        self.assertEqual(ctx.exception.code, "NOT_FOUND")

    async def test_own_active_demo_session_approves(self):
        session_id = uuid4()
        snap = _snapshot(uuid4(), session_id=session_id, session_generation=5)
        repo = ReviewRepo(snap)
        actor = _actor(session_id=session_id, session_generation=5)
        req = ApprovalRequest(enquiry_id=snap.enquiry_id, expected_revision=1, draft_id=snap.draft_id)
        result = await approve(actor, req, uuid4(), repo=repo)
        self.assertEqual(result.revision, 1)

    async def test_unknown_enquiry_404(self):
        repo = ReviewRepo(None)
        req = ApprovalRequest(enquiry_id=uuid4(), expected_revision=1, draft_id=uuid4())
        with self.assertRaises(PartsIQError) as ctx:
            await approve(_actor(), req, uuid4(), repo=repo)
        self.assertEqual(ctx.exception.code, "NOT_FOUND")


# ---------------------------------------------------------------------------
# approve — staff-edited slots go through validate_slots.
# ---------------------------------------------------------------------------
class ApproveStaffEdits(unittest.IsolatedAsyncioTestCase):
    async def test_clean_edited_slots_are_rendered_and_published(self):
        uid = uuid4()
        snap = _snapshot(uid)
        repo = ReviewRepo(snap)
        edited = ReplySlots(
            greeting="Hello", explanation="Your selection is ready for review.", closing="Regards"
        )
        req = ApprovalRequest(
            enquiry_id=snap.enquiry_id, expected_revision=1, draft_id=snap.draft_id, edited_slots=edited
        )
        result = await approve(_actor(uid), req, uuid4(), repo=repo)
        self.assertIsNotNone(result.message_id)

    async def test_edited_slots_with_digit_rejected(self):
        uid = uuid4()
        snap = _snapshot(uid)
        repo = ReviewRepo(snap)
        edited = ReplySlots(greeting="Hi", explanation="We have 3 units ready.", closing="Bye")
        req = ApprovalRequest(
            enquiry_id=snap.enquiry_id, expected_revision=1, draft_id=snap.draft_id, edited_slots=edited
        )
        with self.assertRaises(PartsIQError) as ctx:
            await approve(_actor(uid), req, uuid4(), repo=repo)
        self.assertEqual(ctx.exception.code, "VALIDATION_FAILED")
        self.assertEqual(len(repo.published), 0)

    async def test_edited_slots_with_identifier_rejected(self):
        uid = uuid4()
        snap = _snapshot(uid)
        repo = ReviewRepo(snap)
        edited = ReplySlots(greeting="Hi", explanation="Part VP10 is ready.", closing="Bye")
        req = ApprovalRequest(
            enquiry_id=snap.enquiry_id, expected_revision=1, draft_id=snap.draft_id, edited_slots=edited
        )
        with self.assertRaises(PartsIQError) as ctx:
            await approve(_actor(uid), req, uuid4(), repo=repo)
        self.assertEqual(ctx.exception.code, "VALIDATION_FAILED")


# ---------------------------------------------------------------------------
# reject — records a reason, publishes nothing.
# ---------------------------------------------------------------------------
class Reject(unittest.IsolatedAsyncioTestCase):
    async def test_reject_records_reason_and_publishes_nothing(self):
        uid = uuid4()
        snap = _snapshot(uid)
        repo = ReviewRepo(snap)
        req = RejectionRequest(
            enquiry_id=snap.enquiry_id, expected_revision=1, reason="Wrong part selected"
        )
        result = await reject(_actor(uid), req, uuid4(), repo=repo)
        self.assertEqual(result.status, "rejected")
        self.assertEqual(len(repo.published), 0)  # NO recommendation message
        self.assertEqual(repo.audit[-1]["reason"], "Wrong part selected")

    async def test_reject_stale_revision_409(self):
        uid = uuid4()
        snap = _snapshot(uid, revision=4)
        repo = ReviewRepo(snap)
        req = RejectionRequest(enquiry_id=snap.enquiry_id, expected_revision=2, reason="stale")
        with self.assertRaises(PartsIQError) as ctx:
            await reject(_actor(uid), req, uuid4(), repo=repo)
        self.assertEqual(ctx.exception.code, "STALE_REVISION")

    async def test_reject_double_click_is_idempotent(self):
        uid = uuid4()
        snap = _snapshot(uid)
        repo = ReviewRepo(snap)
        req = RejectionRequest(enquiry_id=snap.enquiry_id, expected_revision=1, reason="no")
        key = uuid4()
        first = await reject(_actor(uid), req, key, repo=repo)
        second = await reject(_actor(uid), req, key, repo=repo)
        self.assertEqual(first.decision_id, second.decision_id)

    async def test_reject_unassigned_reviewer_404(self):
        snap = _snapshot(uuid4())
        repo = ReviewRepo(snap)
        req = RejectionRequest(enquiry_id=snap.enquiry_id, expected_revision=1, reason="no")
        with self.assertRaises(PartsIQError) as ctx:
            await reject(_actor(uuid4()), req, uuid4(), repo=repo)
        self.assertEqual(ctx.exception.code, "NOT_FOUND")


# ---------------------------------------------------------------------------
# F49 Audit trail — same transaction, minimal/redacted, rolls back on failure.
# ---------------------------------------------------------------------------
class AuditTrail(unittest.IsolatedAsyncioTestCase):
    async def test_approval_appends_audit_with_required_fields(self):
        uid = uuid4()
        snap = _snapshot(uid)
        repo = ReviewRepo(snap)
        actor = _actor(uid)
        await approve(
            actor,
            ApprovalRequest(enquiry_id=snap.enquiry_id, expected_revision=1, draft_id=snap.draft_id),
            uuid4(),
            repo=repo,
        )
        self.assertEqual(len(repo.audit), 1)
        event = repo.audit[0]
        for field in ("actor_id", "action", "entity_type", "entity_id", "request_id", "revision"):
            self.assertIn(field, event)
        self.assertEqual(event["actor_id"], str(uid))
        self.assertEqual(event["request_id"], str(actor.request_id))

    async def test_audit_write_failure_rolls_back_approval(self):
        uid = uuid4()
        snap = _snapshot(uid)
        repo = ReviewRepo(snap, audit_fails=True)
        with self.assertRaises(PartsIQError):
            await approve(
                _actor(uid),
                ApprovalRequest(enquiry_id=snap.enquiry_id, expected_revision=1, draft_id=snap.draft_id),
                uuid4(),
                repo=repo,
            )
        self.assertEqual(len(repo.published), 0)  # nothing published when audit fails
        self.assertEqual(len(repo.audit), 0)

    def test_build_audit_event_is_minimal_and_redacted(self):
        uid = uuid4()
        snap = _snapshot(uid)
        event = build_audit_event(_actor(uid), snap, uuid4(), action="approve")
        self.assertIsInstance(event, AuditEvent)
        serialized = str(event.model_dump(mode="json"))
        # No reply prose, citation text or part name leaks into the audit payload.
        for secret in ("rev 1, section", "fuel filter", "<div>"):
            self.assertNotIn(secret, serialized)
        self.assertIn("facts_sha256", event.payload)


# ---------------------------------------------------------------------------
# publication — ApprovedSnapshot + single recommendation + coupling.
# ---------------------------------------------------------------------------
class PubStore:
    """Fake PublicationStore mirroring the one-publication UNIQUE index and decision CHECK."""

    def __init__(self, *, audit_fails=False):
        self.audit_fails = audit_fails
        self.decisions: list[UUID] = []
        self.published: dict[int, UUID] = {}  # revision -> message_id
        self.audit: list[AuditEvent] = []

    async def insert_decision(self, actor, snapshot, decision_id):
        self.decisions.append(decision_id)

    async def insert_recommendation(self, snapshot, decision_id, rendered_text, snapshot_record):
        # DB CHECK: a recommendation must reference an approved decision.
        if decision_id not in self.decisions:
            raise PartsIQError("CONFLICT", internal_detail="recommendation requires a decision_id")
        # UNIQUE(enquiry_id, revision): one recommendation per revision.
        if snapshot.revision in self.published:
            raise PartsIQError("CONFLICT", internal_detail="already published for this revision")
        assert isinstance(snapshot_record, ApprovedSnapshot)
        message_id = uuid4()
        self.published[snapshot.revision] = message_id
        return message_id

    async def append_audit(self, event):
        if self.audit_fails:
            raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="audit write failed")
        self.audit.append(event)


class Publication(unittest.IsolatedAsyncioTestCase):
    async def test_publish_builds_snapshot_and_single_message(self):
        uid = uuid4()
        snap = _snapshot(uid)
        store = PubStore()
        rendered = render_reply(
            ReplySlots(greeting="Hello", explanation="Reviewed.", closing="Thanks"), snap.facts, "en"
        )
        result = await publish_recommendation(_actor(uid), snap, rendered, store=store, now=WHEN)
        self.assertIsNotNone(result.message_id)
        self.assertEqual(len(store.published), 1)
        self.assertEqual(len(store.audit), 1)  # audit appended in the same unit of work

    async def test_publish_audit_failure_propagates(self):
        uid = uuid4()
        snap = _snapshot(uid)
        store = PubStore(audit_fails=True)
        with self.assertRaises(PartsIQError):
            await publish_recommendation(_actor(uid), snap, "<div>r</div>", store=store, now=WHEN)

    def test_build_approved_snapshot_freezes_facts(self):
        snap = _snapshot(uuid4())
        decision_id = uuid4()
        record = build_approved_snapshot(
            snap.facts,
            decision_id=decision_id,
            locale="en",
            reply="<div>r</div>",
            approved_at=WHEN,
            synthetic=True,
        )
        self.assertEqual(record.decision_id, decision_id)
        self.assertEqual(record.facts, snap.facts)
        self.assertTrue(record.synthetic)


# ---------------------------------------------------------------------------
# review — assemble the ReviewView only for an authorized reviewer.
# ---------------------------------------------------------------------------
class ReviewReadRepo:
    def __init__(self, snapshot, parts):
        self.snapshot = snapshot
        self.parts = parts

    async def load_for_review(self, enquiry_id):
        return self.snapshot if self.snapshot and self.snapshot.enquiry_id == enquiry_id else None

    async def load_view_parts(self, enquiry_id):
        return self.parts


def _enquiry_view(enquiry_id, revision=1):
    return EnquiryView(
        id=enquiry_id,
        revision=revision,
        status="awaiting_review",
        messages=[],
        item_ids=[],
        catalogue_version_id=uuid4(),
        updated_at=WHEN,
    )


class ReviewViewAssembly(unittest.IsolatedAsyncioTestCase):
    async def test_assembles_view_for_assigned_reviewer(self):
        uid = uuid4()
        snap = _snapshot(uid)
        verification = VerificationResult(passed=True, failures=[], facts_sha256=facts_sha256(snap.facts))
        parts = (
            _enquiry_view(snap.enquiry_id),
            snap.facts,
            ReplySlots(greeting="Hello", explanation="Reviewed.", closing="Thanks"),
            verification,
        )
        repo = ReviewReadRepo(snap, parts)
        view = await load_review_view(_actor(uid), snap.enquiry_id, repo=repo)
        self.assertIsInstance(view, ReviewView)
        self.assertEqual(view.assigned_to, uid)
        self.assertEqual(view.facts, snap.facts)
        self.assertTrue(view.verification.passed)

    async def test_missing_panels_are_none(self):
        uid = uuid4()
        snap = _snapshot(uid)
        parts = (_enquiry_view(snap.enquiry_id), None, None, None)
        repo = ReviewReadRepo(snap, parts)
        view = await load_review_view(_actor(uid), snap.enquiry_id, repo=repo)
        self.assertIsNone(view.facts)
        self.assertIsNone(view.draft)
        self.assertIsNone(view.verification)

    async def test_unassigned_reviewer_gets_404(self):
        snap = _snapshot(uuid4())
        parts = (_enquiry_view(snap.enquiry_id), None, None, None)
        repo = ReviewReadRepo(snap, parts)
        with self.assertRaises(PartsIQError) as ctx:
            await load_review_view(_actor(uuid4()), snap.enquiry_id, repo=repo)
        self.assertEqual(ctx.exception.code, "NOT_FOUND")


# ---------------------------------------------------------------------------
# revise — increments revision + immutable snapshot, never mutates a prior approval (F40).
# ---------------------------------------------------------------------------
class RevisionRepo:
    """Fake RevisionRepository: append-only history; a prior approval is never touched."""

    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.revision = snapshot.revision if snapshot else 0
        # The prior revision's approval, frozen; the fake rejects any mutation of it.
        self.approvals: dict[int, UUID] = {self.revision: uuid4()} if snapshot else {}
        self.snapshots: dict[int, dict] = {}

    async def load_for_review(self, enquiry_id):
        return self.snapshot if self.snapshot and self.snapshot.enquiry_id == enquiry_id else None

    async def apply_revision(self, actor, snapshot, request):
        prior_approvals = dict(self.approvals)  # capture to assert immutability
        self.revision = snapshot.revision + 1
        # Append an immutable before/after snapshot for the correction (never overwrite).
        self.snapshots[self.revision] = {
            "from_revision": snapshot.revision,
            "corrections": [c.model_dump(mode="json") for c in request.corrections],
            "reason": request.reason,
        }
        # The new revision has NO approval; historical approvals are untouched (F40).
        assert self.approvals == prior_approvals
        return EnquiryView(
            id=snapshot.enquiry_id,
            revision=self.revision,
            status="processing",
            messages=[],
            item_ids=[c.item_id for c in request.corrections],
            catalogue_version_id=snapshot.catalogue_version_id,
            updated_at=WHEN,
        )


class Revise(unittest.IsolatedAsyncioTestCase):
    async def test_revise_increments_revision_and_snapshots(self):
        uid = uuid4()
        snap = _snapshot(uid, revision=2)
        repo = RevisionRepo(snap)
        item_id = snap.facts.items[0].item_id
        req = RevisionRequest(
            enquiry_id=snap.enquiry_id,
            expected_revision=2,
            corrections=[ItemCorrection(item_id=item_id, quantity=Decimal("5"))],
            reason="Customer corrected the quantity",
        )
        view = await revise(_actor(uid), req, repo=repo)
        self.assertEqual(view.revision, 3)
        self.assertEqual(view.status, "processing")
        self.assertIn(3, repo.snapshots)
        self.assertEqual(repo.snapshots[3]["from_revision"], 2)

    async def test_revise_never_mutates_prior_approval(self):
        # F40: the prior approved revision's decision is preserved after a correction.
        uid = uuid4()
        snap = _snapshot(uid, revision=2)
        repo = RevisionRepo(snap)
        before = dict(repo.approvals)
        req = RevisionRequest(
            enquiry_id=snap.enquiry_id,
            expected_revision=2,
            corrections=[ItemCorrection(item_id=snap.facts.items[0].item_id, model_text="CAT-320")],
            reason="fix model",
        )
        await revise(_actor(uid), req, repo=repo)
        self.assertEqual(repo.approvals, before)  # old approval untouched

    async def test_revise_stale_revision_409(self):
        uid = uuid4()
        snap = _snapshot(uid, revision=5)
        repo = RevisionRepo(snap)
        req = RevisionRequest(
            enquiry_id=snap.enquiry_id,
            expected_revision=4,
            corrections=[ItemCorrection(item_id=uuid4(), quantity=Decimal("1"))],
            reason="late",
        )
        with self.assertRaises(PartsIQError) as ctx:
            await revise(_actor(uid), req, repo=repo)
        self.assertEqual(ctx.exception.code, "STALE_REVISION")

    async def test_revise_foreign_actor_404(self):
        snap = _snapshot(uuid4(), revision=1)  # owner + assignee is someone else
        repo = RevisionRepo(snap)
        req = RevisionRequest(
            enquiry_id=snap.enquiry_id,
            expected_revision=1,
            corrections=[ItemCorrection(item_id=uuid4(), quantity=Decimal("1"))],
            reason="x",
        )
        with self.assertRaises(PartsIQError) as ctx:
            await revise(_actor(uuid4()), req, repo=repo)
        self.assertEqual(ctx.exception.code, "NOT_FOUND")

    async def test_revise_own_demo_session(self):
        session_id = uuid4()
        snap = _snapshot(uuid4(), revision=1, session_id=session_id, session_generation=3)
        repo = RevisionRepo(snap)
        actor = _actor(session_id=session_id, session_generation=3)
        req = RevisionRequest(
            enquiry_id=snap.enquiry_id,
            expected_revision=1,
            corrections=[ItemCorrection(item_id=snap.facts.items[0].item_id, quantity=Decimal("4"))],
            reason="demo fix",
        )
        view = await revise(actor, req, repo=repo)
        self.assertEqual(view.revision, 2)


# ---------------------------------------------------------------------------
# Live DB path — BLOCKED. Never faked; only runs under an explicit opt-in.
# ---------------------------------------------------------------------------
@unittest.skipUnless(
    os.environ.get("PARTSIQ_LIVE_DB") == "1",
    "live review/approval Postgres adapter is BLOCKED; set PARTSIQ_LIVE_DB=1 to run",
)
class LiveApprovalTransaction(unittest.IsolatedAsyncioTestCase):  # pragma: no cover
    async def test_live_single_publication_unique_index(self):
        raise AssertionError("live DB path is BLOCKED and must never run in CI")


if __name__ == "__main__":
    unittest.main(verbosity=2)
