"""F39 Review actions — approve only a verified current draft; double-click publishes once.

A concurrent edit (stale expected revision) defeats a stale approval, and a failed
re-verification blocks publication. Exercises the orchestrator approve use case.
"""
from __future__ import annotations

import unittest
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from app.approval import ReviewSnapshot, StoredDecision, _canonical_hash, approve
from app.verification import canonical_facts_sha256
from partsiq_common.contracts import (
    ActorContext,
    Allocation,
    ApprovalRequest,
    ApprovalResult,
    CandidateEvidence,
    StockEvidence,
    VerificationEvidence,
    VerifiedFacts,
    VerifiedItem,
)
from partsiq_common.errors import PartsIQError

WHEN = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _facts(enquiry_id, revision=1):
    return VerifiedFacts(
        enquiry_id=enquiry_id, revision=revision, catalogue_version_id=uuid4(),
        items=[VerifiedItem(
            item_id=uuid4(), configuration_id=100, part_id=10, part_number="VP-FF-10",
            name_en="fuel filter", name_ar="فلتر وقود", requested_quantity=Decimal("2"),
            allocations=[Allocation(warehouse_id=1, quantity=Decimal("2"), transfer_days=2, stock_updated_at=WHEN)],
            shortage=Decimal("0"), source_reference="SYNTH-CA-PB-CA-110 rev 1, section FILTERS", evidence_id=uuid4(),
        )],
    )


def _evidence(facts, *, passes=True):
    agg = defaultdict(lambda: Decimal("0"))
    cands = []
    for it in facts.items:
        cands.append(CandidateEvidence(item_id=it.item_id, part_id=it.part_id, configuration_id=it.configuration_id,
                                       evidence_id=it.evidence_id, source_reference=it.source_reference))
        for a in it.allocations:
            agg[(it.part_id, a.warehouse_id)] += a.quantity
    stock = [StockEvidence(part_id=p, warehouse_id=w, available=q, updated_at=WHEN) for (p, w), q in agg.items()]
    return VerificationEvidence(current_revision=facts.revision, candidates=cands, stock=stock,
                                active_catalogue_version_id=facts.catalogue_version_id if passes else uuid4())


def _snap(uid, facts):
    return ReviewSnapshot(
        enquiry_id=facts.enquiry_id, revision=facts.revision, catalogue_version_id=facts.catalogue_version_id,
        status="awaiting_review", draft_id=uuid4(), facts=facts, verification_id=uuid4(), verification_passed=True,
        facts_sha256=canonical_facts_sha256(facts), locale="en", rendered_text="<div>r</div>",
        assigned_to=uid, owner_id=uid,
    )


class Repo:
    def __init__(self, snap, *, passes=True):
        self.snap = snap
        self.passes = passes
        self.by_key = {}
        self.published = {}

    async def load_for_review(self, enquiry_id):
        return self.snap

    async def find_decision_by_key(self, enquiry_id, key):
        return self.by_key.get(key)

    async def refresh_evidence(self, snapshot):
        return _evidence(snapshot.facts, passes=self.passes)

    async def commit_approval(self, actor, snapshot, request, key, rendered_text):
        self.published[snapshot.revision] = uuid4()
        result = ApprovalResult(decision_id=uuid4(), message_id=self.published[snapshot.revision],
                                revision=snapshot.revision, already_applied=False)
        self.by_key[key] = StoredDecision(request_hash=_canonical_hash(request.model_dump(mode="json")), approval=result)
        return result


def _actor(uid):
    return ActorContext(user_id=uid, request_id=uuid4(), roles=["reviewer"])


class ReviewActions(unittest.IsolatedAsyncioTestCase):
    async def test_approve_verified_current(self):
        uid = uuid4()
        facts = _facts(uuid4())
        repo = Repo(_snap(uid, facts))
        req = ApprovalRequest(enquiry_id=facts.enquiry_id, expected_revision=1, draft_id=repo.snap.draft_id)
        result = await approve(_actor(uid), req, uuid4(), repo=repo)
        self.assertFalse(result.already_applied)

    async def test_double_click_publishes_once(self):
        uid = uuid4()
        facts = _facts(uuid4())
        repo = Repo(_snap(uid, facts))
        req = ApprovalRequest(enquiry_id=facts.enquiry_id, expected_revision=1, draft_id=repo.snap.draft_id)
        key = uuid4()
        await approve(_actor(uid), req, key, repo=repo)
        second = await approve(_actor(uid), req, key, repo=repo)
        self.assertTrue(second.already_applied)
        self.assertEqual(len(repo.published), 1)

    async def test_stale_revision_blocks(self):
        uid = uuid4()
        facts = _facts(uuid4(), revision=2)
        repo = Repo(_snap(uid, facts))
        req = ApprovalRequest(enquiry_id=facts.enquiry_id, expected_revision=1, draft_id=repo.snap.draft_id)
        with self.assertRaises(PartsIQError) as ctx:
            await approve(_actor(uid), req, uuid4(), repo=repo)
        self.assertEqual(ctx.exception.code, "STALE_REVISION")

    async def test_failed_verification_blocks_publication(self):
        uid = uuid4()
        facts = _facts(uuid4())
        repo = Repo(_snap(uid, facts), passes=False)
        req = ApprovalRequest(enquiry_id=facts.enquiry_id, expected_revision=1, draft_id=repo.snap.draft_id)
        with self.assertRaises(PartsIQError):
            await approve(_actor(uid), req, uuid4(), repo=repo)
        self.assertEqual(len(repo.published), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
