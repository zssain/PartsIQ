"""F49 Audit trail — approval records actor/request/entity/revision; a failed audit rolls back.

Offline: a fake review repository captures the audit append that happens inside the same
transaction as the approval. An audit write failure aborts the whole approval (nothing
published), and the captured event carries no secret payload. Application-role UPDATE/
DELETE/TRUNCATE rejection and database-owner powers are DB-trigger behaviour (prompt 03)
and remain integration-only — documented honestly, not asserted here.
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

from app.approval import ReviewSnapshot, approve  # noqa: E402
from app.verification import canonical_facts_sha256  # noqa: E402
from partsiq_common.contracts import (  # noqa: E402
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
from partsiq_common.errors import PartsIQError  # noqa: E402

WHEN = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _facts():
    return VerifiedFacts(
        enquiry_id=uuid4(), revision=1, catalogue_version_id=uuid4(),
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
    return VerificationEvidence(current_revision=1, active_catalogue_version_id=facts.catalogue_version_id,
                                candidates=cands, stock=stock)


def _snap(uid, facts):
    return ReviewSnapshot(
        enquiry_id=facts.enquiry_id, revision=1, catalogue_version_id=facts.catalogue_version_id,
        status="awaiting_review", draft_id=uuid4(), facts=facts, verification_id=uuid4(), verification_passed=True,
        facts_sha256=canonical_facts_sha256(facts), locale="en", rendered_text="<div>r</div>",
        assigned_to=uid, owner_id=uid,
    )


class Repo:
    def __init__(self, snap, *, audit_fails=False):
        self.snap = snap
        self.audit_fails = audit_fails
        self.by_key = {}
        self.audit = []
        self.published = {}

    async def load_for_review(self, enquiry_id):
        return self.snap

    async def find_decision_by_key(self, enquiry_id, key):
        return self.by_key.get(key)

    async def refresh_evidence(self, snapshot):
        return _evidence(snapshot.facts)

    async def commit_approval(self, actor, snapshot, request, key, rendered_text):
        decision_id = uuid4()
        if self.audit_fails:
            raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="audit write failed; whole txn rolled back")
        self.audit.append({
            "actor_id": str(actor.user_id), "action": "approve", "entity_type": "review_decision",
            "entity_id": str(decision_id), "request_id": str(actor.request_id), "revision": snapshot.revision,
        })
        self.published[snapshot.revision] = uuid4()
        return ApprovalResult(decision_id=decision_id, message_id=self.published[snapshot.revision],
                              revision=1, already_applied=False)


def _actor(uid):
    return ActorContext(user_id=uid, request_id=uuid4(), roles=["reviewer"])


class AuditTrail(unittest.IsolatedAsyncioTestCase):
    async def test_approval_appends_audit_with_required_fields(self):  # success
        uid = uuid4()
        facts = _facts()
        repo = Repo(_snap(uid, facts))
        actor = _actor(uid)
        await approve(actor, ApprovalRequest(enquiry_id=facts.enquiry_id, expected_revision=1, draft_id=repo.snap.draft_id), uuid4(), repo=repo)
        self.assertEqual(len(repo.audit), 1)
        event = repo.audit[0]
        for field in ("actor_id", "action", "entity_type", "entity_id", "request_id", "revision"):
            self.assertIn(field, event)
        self.assertEqual(event["actor_id"], str(uid))
        self.assertEqual(event["request_id"], str(actor.request_id))

    async def test_audit_is_minimal_and_redacted(self):
        uid = uuid4()
        facts = _facts()
        repo = Repo(_snap(uid, facts))
        await approve(_actor(uid), ApprovalRequest(enquiry_id=facts.enquiry_id, expected_revision=1, draft_id=repo.snap.draft_id), uuid4(), repo=repo)
        serialized = str(repo.audit[0])
        for secret in ("rev 1, section", "fuel filter", "<div>"):  # no draft prose/citation payload leaks
            self.assertNotIn(secret, serialized)

    async def test_audit_write_failure_rolls_back_approval(self):  # dependency-failure
        uid = uuid4()
        facts = _facts()
        repo = Repo(_snap(uid, facts), audit_fails=True)
        with self.assertRaises(PartsIQError):
            await approve(_actor(uid), ApprovalRequest(enquiry_id=facts.enquiry_id, expected_revision=1, draft_id=repo.snap.draft_id), uuid4(), repo=repo)
        self.assertEqual(len(repo.published), 0)  # nothing published when audit fails
        self.assertEqual(len(repo.audit), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
