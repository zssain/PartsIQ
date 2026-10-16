"""F40 Approval invalidation — approval is bound to revision AND verified fact hash.

An old approval cannot authorize a new revision, and a plan whose verified fact hash no
longer matches the current facts cannot be published.
"""
from __future__ import annotations

import unittest
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from app.approval import ReviewSnapshot, approve
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


def _evidence(facts):
    agg = defaultdict(lambda: Decimal("0"))
    cands = []
    for it in facts.items:
        cands.append(CandidateEvidence(item_id=it.item_id, part_id=it.part_id, configuration_id=it.configuration_id,
                                       evidence_id=it.evidence_id, source_reference=it.source_reference))
        for a in it.allocations:
            agg[(it.part_id, a.warehouse_id)] += a.quantity
    stock = [StockEvidence(part_id=p, warehouse_id=w, available=q, updated_at=WHEN) for (p, w), q in agg.items()]
    return VerificationEvidence(current_revision=facts.revision, active_catalogue_version_id=facts.catalogue_version_id,
                                candidates=cands, stock=stock)


def _snapshot(actor_id, *, revision=1, drift=False):
    facts = _facts(uuid4(), revision)
    return ReviewSnapshot(
        enquiry_id=facts.enquiry_id, revision=revision, catalogue_version_id=facts.catalogue_version_id,
        status="awaiting_review", draft_id=uuid4(), facts=facts, verification_id=uuid4(), verification_passed=True,
        facts_sha256="0" * 64 if drift else canonical_facts_sha256(facts), locale="en",
        rendered_text="<div>r</div>", assigned_to=actor_id, owner_id=actor_id,
    )


class Repo:
    def __init__(self, snap):
        self.snap = snap
        self.by_key = {}
        self.published = {}

    async def load_for_review(self, enquiry_id):
        return self.snap

    async def find_decision_by_key(self, enquiry_id, key):
        return self.by_key.get(key)

    async def refresh_evidence(self, snapshot):
        return _evidence(snapshot.facts)

    async def commit_approval(self, actor, snapshot, request, key, rendered_text):
        self.published[snapshot.revision] = uuid4()
        return ApprovalResult(decision_id=uuid4(), message_id=self.published[snapshot.revision],
                              revision=snapshot.revision, already_applied=False)


def _actor(uid):
    return ActorContext(user_id=uid, request_id=uuid4(), roles=["reviewer"])


class ApprovalInvalidation(unittest.IsolatedAsyncioTestCase):
    async def test_current_revision_approves(self):  # success
        uid = uuid4()
        snap = _snapshot(uid, revision=2)
        repo = Repo(snap)
        req = ApprovalRequest(enquiry_id=snap.enquiry_id, expected_revision=2, draft_id=snap.draft_id)
        result = await approve(_actor(uid), req, uuid4(), repo=repo)
        self.assertEqual(result.revision, 2)

    async def test_old_approval_cannot_authorize_new_revision(self):  # stale-revision
        uid = uuid4()
        snap = _snapshot(uid, revision=3)  # current is 3
        repo = Repo(snap)
        req = ApprovalRequest(enquiry_id=snap.enquiry_id, expected_revision=2, draft_id=snap.draft_id)
        with self.assertRaises(PartsIQError) as ctx:
            await approve(_actor(uid), req, uuid4(), repo=repo)
        self.assertEqual(ctx.exception.code, "STALE_REVISION")
        self.assertEqual(len(repo.published), 0)

    async def test_fact_hash_drift_blocks_publication(self):  # invalid-input / changed plan
        uid = uuid4()
        snap = _snapshot(uid, drift=True)
        repo = Repo(snap)
        req = ApprovalRequest(enquiry_id=snap.enquiry_id, expected_revision=1, draft_id=snap.draft_id)
        with self.assertRaises(PartsIQError) as ctx:
            await approve(_actor(uid), req, uuid4(), repo=repo)
        self.assertEqual(ctx.exception.code, "CONFLICT")

    async def test_wrong_draft_id_blocks(self):
        uid = uuid4()
        snap = _snapshot(uid)
        repo = Repo(snap)
        req = ApprovalRequest(enquiry_id=snap.enquiry_id, expected_revision=1, draft_id=uuid4())
        with self.assertRaises(PartsIQError):
            await approve(_actor(uid), req, uuid4(), repo=repo)


if __name__ == "__main__":
    unittest.main(verbosity=2)
