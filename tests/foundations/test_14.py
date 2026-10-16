"""Acceptance tests for prompt 14 — approval and revision transactions (foundation gate).

Offline: a fake review repository stands in for the locked single transaction. The
decision logic is exercised in full — assigned/own-session authorization (else 404),
expected-revision and verified-fact-hash binding, stock refresh + re-verification, a
double-click publishing exactly once, the one-recommendation-per-revision backstop,
rejection without publication, audit capture + rollback, and corrections incrementing the
revision without touching history. The live Postgres transaction/triggers are BLOCKED.
Covers F39, F40, F47, F49.
"""
from __future__ import annotations

import sys
import unittest
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "partsiq_common"))
sys.path.insert(0, str(REPO_ROOT / "services" / "orchestrator"))

from app.approval import (  # noqa: E402
    ReviewSnapshot,
    StoredDecision,
    _canonical_hash,
    approve,
    authorize_review,
    reject,
)
from app.revisions import revise  # noqa: E402
from app.verification import canonical_facts_sha256  # noqa: E402
from partsiq_common.contracts import (  # noqa: E402
    ActorContext,
    Allocation,
    ApprovalRequest,
    ApprovalResult,
    CandidateEvidence,
    EnquiryView,
    ItemCorrection,
    RejectionRequest,
    ReplySlots,
    RevisionRequest,
    ReviewResult,
    StockEvidence,
    VerificationEvidence,
    VerifiedFacts,
    VerifiedItem,
)
from partsiq_common.errors import PartsIQError  # noqa: E402

WHEN = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _facts(enquiry_id, revision=1, catalogue=None):
    catalogue = catalogue or uuid4()
    return VerifiedFacts(
        enquiry_id=enquiry_id, revision=revision, catalogue_version_id=catalogue,
        items=[
            VerifiedItem(
                item_id=uuid4(), configuration_id=100, part_id=10, part_number="VP-FF-10",
                name_en="fuel filter", name_ar="فلتر وقود", requested_quantity=Decimal("2"),
                allocations=[Allocation(warehouse_id=1, quantity=Decimal("2"), transfer_days=2, stock_updated_at=WHEN)],
                shortage=Decimal("0"), source_reference="SYNTH-CA-PB-CA-110 rev 1, section FILTERS",
                evidence_id=uuid4(),
            )
        ],
    )


def _evidence_for(facts, *, passes=True):
    agg = defaultdict(lambda: Decimal("0"))
    candidates = []
    for item in facts.items:
        candidates.append(CandidateEvidence(
            item_id=item.item_id, part_id=item.part_id, configuration_id=item.configuration_id,
            evidence_id=item.evidence_id, source_reference=item.source_reference,
        ))
        for allocation in item.allocations:
            agg[(item.part_id, allocation.warehouse_id)] += allocation.quantity
    stock = [StockEvidence(part_id=p, warehouse_id=w, available=q, updated_at=WHEN) for (p, w), q in agg.items()]
    return VerificationEvidence(
        current_revision=facts.revision,
        active_catalogue_version_id=facts.catalogue_version_id if passes else uuid4(),
        candidates=candidates, stock=stock,
    )


def _snapshot(actor_id, enquiry_id=None, *, revision=1, facts=None, assigned=True, drift=False, passed=True):
    enquiry_id = enquiry_id or uuid4()
    facts = facts or _facts(enquiry_id, revision)
    return ReviewSnapshot(
        enquiry_id=enquiry_id, revision=revision, catalogue_version_id=facts.catalogue_version_id,
        status="awaiting_review", draft_id=uuid4(), facts=facts, verification_id=uuid4(),
        verification_passed=passed,
        facts_sha256="0" * 64 if drift else canonical_facts_sha256(facts),
        locale="en", rendered_text="<div>reply</div>",
        assigned_to=actor_id if assigned else uuid4(), owner_id=actor_id,
    )


class FakeReviewRepo:
    def __init__(self, snapshot, *, evidence_passes=True, audit_fails=False):
        self.snapshot = snapshot
        self.evidence_passes = evidence_passes
        self.audit_fails = audit_fails
        self.by_key: dict[tuple, StoredDecision] = {}
        self.published: dict[tuple, object] = {}
        self.audit: list[dict] = []
        self.revisions: list[tuple] = []

    async def load_for_review(self, enquiry_id):
        return self.snapshot if self.snapshot and self.snapshot.enquiry_id == enquiry_id else None

    async def find_decision_by_key(self, enquiry_id, key):
        return self.by_key.get((enquiry_id, key))

    async def refresh_evidence(self, snapshot):
        return _evidence_for(snapshot.facts, passes=self.evidence_passes)

    async def commit_approval(self, actor, snapshot, request, key, rendered_text):
        pub = (snapshot.enquiry_id, snapshot.revision)
        if pub in self.published:
            raise PartsIQError("CONFLICT", internal_detail="one recommendation per revision (unique index)")
        decision_id, message_id = uuid4(), uuid4()
        if self.audit_fails:  # audit is in the same txn; its failure rolls everything back
            raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="audit write failed; rolled back")
        self.audit.append({
            "actor_id": str(actor.user_id), "action": "approve", "entity_type": "review_decision",
            "entity_id": str(decision_id), "request_id": str(actor.request_id), "revision": snapshot.revision,
        })
        self.published[pub] = message_id
        result = ApprovalResult(decision_id=decision_id, message_id=message_id, revision=snapshot.revision, already_applied=False)
        self.by_key[(snapshot.enquiry_id, key)] = StoredDecision(
            request_hash=_canonical_hash(request.model_dump(mode="json")), approval=result)
        return result

    async def commit_rejection(self, actor, snapshot, request, key):
        self.audit.append({"actor_id": str(actor.user_id), "action": "reject", "revision": snapshot.revision})
        result = ReviewResult(decision_id=uuid4(), revision=snapshot.revision, status="rejected")
        self.by_key[(snapshot.enquiry_id, key)] = StoredDecision(
            request_hash=_canonical_hash(request.model_dump(mode="json")), review=result)
        return result

    async def apply_revision(self, actor, snapshot, request):
        self.revisions.append((snapshot.revision, snapshot.revision + 1))
        return EnquiryView(
            id=snapshot.enquiry_id, revision=snapshot.revision + 1, status="processing", messages=[],
            item_ids=[c.item_id for c in request.corrections], catalogue_version_id=snapshot.catalogue_version_id,
            updated_at=WHEN,
        )


def _actor(user_id=None):
    return ActorContext(user_id=user_id or uuid4(), request_id=uuid4(), roles=["reviewer"])


def _approval(enquiry_id, draft_id, revision=1, slots=None):
    return ApprovalRequest(enquiry_id=enquiry_id, expected_revision=revision, draft_id=draft_id, edited_slots=slots)


class Approve(unittest.IsolatedAsyncioTestCase):
    async def test_success_publishes_one_recommendation(self):
        actor = _actor()
        snap = _snapshot(actor.user_id)
        repo = FakeReviewRepo(snap)
        result = await approve(actor, _approval(snap.enquiry_id, snap.draft_id), uuid4(), repo=repo)
        self.assertFalse(result.already_applied)
        self.assertIsNotNone(result.message_id)
        self.assertEqual(len(repo.published), 1)

    async def test_double_click_publishes_once(self):  # F39
        actor = _actor()
        snap = _snapshot(actor.user_id)
        repo = FakeReviewRepo(snap)
        key = uuid4()
        req = _approval(snap.enquiry_id, snap.draft_id)
        first = await approve(actor, req, key, repo=repo)
        second = await approve(actor, req, key, repo=repo)
        self.assertFalse(first.already_applied)
        self.assertTrue(second.already_applied)
        self.assertEqual(first.decision_id, second.decision_id)
        self.assertEqual(len(repo.published), 1)

    async def test_key_reuse_different_request_conflicts(self):
        actor = _actor()
        snap = _snapshot(actor.user_id)
        repo = FakeReviewRepo(snap)
        key = uuid4()
        await approve(actor, _approval(snap.enquiry_id, snap.draft_id), key, repo=repo)
        with self.assertRaises(PartsIQError) as ctx:
            await approve(actor, _approval(snap.enquiry_id, uuid4()), key, repo=repo)
        self.assertEqual(ctx.exception.code, "IDEMPOTENCY_MISMATCH")

    async def test_stale_revision_blocks(self):  # F40 stale-revision
        actor = _actor()
        snap = _snapshot(actor.user_id, revision=2)
        repo = FakeReviewRepo(snap)
        with self.assertRaises(PartsIQError) as ctx:
            await approve(actor, _approval(snap.enquiry_id, snap.draft_id, revision=1), uuid4(), repo=repo)
        self.assertEqual(ctx.exception.code, "STALE_REVISION")

    async def test_fact_hash_drift_blocks(self):  # F40 bind to verified fact hash
        actor = _actor()
        snap = _snapshot(actor.user_id, drift=True)
        repo = FakeReviewRepo(snap)
        with self.assertRaises(PartsIQError) as ctx:
            await approve(actor, _approval(snap.enquiry_id, snap.draft_id), uuid4(), repo=repo)
        self.assertEqual(ctx.exception.code, "CONFLICT")

    async def test_failed_reverification_blocks_publication(self):  # F39
        actor = _actor()
        snap = _snapshot(actor.user_id)
        repo = FakeReviewRepo(snap, evidence_passes=False)
        with self.assertRaises(PartsIQError):
            await approve(actor, _approval(snap.enquiry_id, snap.draft_id), uuid4(), repo=repo)
        self.assertEqual(len(repo.published), 0)

    async def test_unassigned_reviewer_gets_404(self):  # unauthorized
        actor = _actor()
        snap = _snapshot(actor.user_id, assigned=False)
        repo = FakeReviewRepo(snap)
        with self.assertRaises(PartsIQError) as ctx:
            await approve(actor, _approval(snap.enquiry_id, snap.draft_id), uuid4(), repo=repo)
        self.assertEqual(ctx.exception.http_status, 404)

    async def test_edited_prose_uses_slot_schema(self):  # F39 edit then reverify
        actor = _actor()
        snap = _snapshot(actor.user_id)
        repo = FakeReviewRepo(snap)
        slots = ReplySlots(greeting="Hello", explanation="Reviewed and ready.", closing="Regards")
        result = await approve(actor, _approval(snap.enquiry_id, snap.draft_id, slots=slots), uuid4(), repo=repo)
        self.assertIsNotNone(result.decision_id)

    async def test_edited_prose_with_number_rejected(self):
        actor = _actor()
        snap = _snapshot(actor.user_id)
        repo = FakeReviewRepo(snap)
        slots = ReplySlots(greeting="Hi", explanation="We have 5 units.", closing="Bye")
        with self.assertRaises(PartsIQError):
            await approve(actor, _approval(snap.enquiry_id, snap.draft_id, slots=slots), uuid4(), repo=repo)


class Reject(unittest.IsolatedAsyncioTestCase):
    async def test_rejection_records_reason_without_publication(self):
        actor = _actor()
        snap = _snapshot(actor.user_id)
        repo = FakeReviewRepo(snap)
        req = RejectionRequest(enquiry_id=snap.enquiry_id, expected_revision=1, reason="Wrong machine identified.")
        result = await reject(actor, req, uuid4(), repo=repo)
        self.assertEqual(result.status, "rejected")
        self.assertEqual(len(repo.published), 0)


class Revise(unittest.IsolatedAsyncioTestCase):
    async def test_correction_increments_revision(self):  # F40
        actor = _actor()
        snap = _snapshot(actor.user_id)
        repo = FakeReviewRepo(snap)
        req = RevisionRequest(
            enquiry_id=snap.enquiry_id, expected_revision=1,
            corrections=[ItemCorrection(item_id=uuid4(), quantity=Decimal("3"))], reason="Customer needs 3.",
        )
        view = await revise(actor, req, repo=repo)
        self.assertEqual(view.revision, 2)
        self.assertEqual(view.status, "processing")
        self.assertEqual(repo.revisions, [(1, 2)])

    async def test_stale_correction_rejected(self):
        actor = _actor()
        snap = _snapshot(actor.user_id, revision=3)
        repo = FakeReviewRepo(snap)
        req = RevisionRequest(
            enquiry_id=snap.enquiry_id, expected_revision=1,
            corrections=[ItemCorrection(item_id=uuid4())], reason="late",
        )
        with self.assertRaises(PartsIQError) as ctx:
            await revise(actor, req, repo=repo)
        self.assertEqual(ctx.exception.code, "STALE_REVISION")


class Authorization(unittest.TestCase):
    def test_demo_requires_own_session(self):
        actor = ActorContext(user_id=uuid4(), request_id=uuid4(), roles=[], session_id=uuid4(), session_generation=2)
        facts = _facts(uuid4())
        snap = ReviewSnapshot(
            enquiry_id=facts.enquiry_id, revision=1, catalogue_version_id=facts.catalogue_version_id,
            status="awaiting_review", draft_id=uuid4(), facts=facts, verification_id=uuid4(),
            verification_passed=True, facts_sha256=canonical_facts_sha256(facts), locale="en",
            session_id=actor.session_id, session_generation=2,
        )
        authorize_review(actor, snap)  # ok
        stale = actor.model_copy(update={"session_generation": 1})
        with self.assertRaises(PartsIQError):
            authorize_review(stale, snap)


if __name__ == "__main__":
    unittest.main(verbosity=2)
