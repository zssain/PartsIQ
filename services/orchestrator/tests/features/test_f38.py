"""F38 Correct extracted details — typed corrections through the locked revision machinery.

Increments the revision and invalidates derived state (via the port); a correction can never
set approved status or invent a candidate fact; an empty correction is 422; a stale revision is
409; a foreign actor is 404.
"""
from __future__ import annotations

import unittest
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from app.approval import ReviewSnapshot
from app.features.f38_correct_extracted_details import F38Request, correct_extraction
from app.handlers import reset_derived_state
from partsiq_common.contracts import (
    ActorContext,
    EnquiryState,
    EnquiryView,
    ItemCorrection,
    ItemInput,
    ItemState,
    RevisionRequest,
    VerifiedFacts,
    VerifiedItem,
)
from partsiq_common.errors import PartsIQError

WHEN = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _actor(user_id=None):
    return ActorContext(user_id=user_id or uuid4(), request_id=uuid4(), roles=["reviewer"])


def _facts(enquiry_id, revision=1):
    return VerifiedFacts(
        enquiry_id=enquiry_id, revision=revision, catalogue_version_id=uuid4(),
        items=[VerifiedItem(
            item_id=uuid4(), configuration_id=100, part_id=10, part_number="VP-10",
            name_en="fuel filter", name_ar="فلتر", requested_quantity=Decimal("2"), allocations=[],
            shortage=Decimal("2"), source_reference="SYNTH-CA rev 1, section FILTERS", evidence_id=uuid4(),
        )],
    )


def _snapshot(owner, revision=1):
    enquiry_id = uuid4()
    return ReviewSnapshot(
        enquiry_id=enquiry_id, revision=revision, catalogue_version_id=uuid4(), status="awaiting_review",
        draft_id=uuid4(), facts=_facts(enquiry_id, revision), verification_id=uuid4(), verification_passed=True,
        facts_sha256="x" * 64, locale="en", rendered_text="…", assigned_to=owner, owner_id=owner,
    )


def _change(enquiry_id, revision=1, correction=None):
    return RevisionRequest(
        enquiry_id=enquiry_id, expected_revision=revision,
        corrections=[correction or ItemCorrection(item_id=uuid4(), serial_text="000150")],
        reason="corrected serial from the nameplate",
    )


class FakeRevisionRepo:
    def __init__(self, snapshot, *, result_status="processing", raises=None):
        self._snapshot = snapshot
        self._status = result_status
        self._raises = raises
        self.applied = False
        self.before = None
        self.after = None
        self.enqueued = False

    async def load_for_review(self, enquiry_id):
        if self._raises is not None:
            raise self._raises
        return self._snapshot

    async def apply_revision(self, actor, snapshot, request):
        self.applied = True
        self.before = snapshot.revision          # record before
        self.after = snapshot.revision + 1        # record after
        self.enqueued = True                      # recomputation enqueued
        return EnquiryView(
            id=snapshot.enquiry_id, revision=snapshot.revision + 1, status=self._status, messages=[],
            item_ids=[], catalogue_version_id=snapshot.catalogue_version_id, updated_at=WHEN,
        )


class CorrectExtraction(unittest.IsolatedAsyncioTestCase):
    async def test_applies_correction_and_increments_revision(self):
        owner = _actor()
        snap = _snapshot(owner.user_id)
        repo = FakeRevisionRepo(snap)
        result = await correct_extraction(owner, F38Request(change=_change(snap.enquiry_id)), repo=repo)
        self.assertEqual(result.enquiry.revision, 2)       # incremented
        self.assertEqual(result.enquiry.status, "processing")  # never approved
        self.assertTrue(repo.applied and repo.enqueued)    # recomputation enqueued
        self.assertNotEqual(repo.before, repo.after)       # before/after recorded

    async def test_empty_correction_rejected(self):
        owner = _actor()
        snap = _snapshot(owner.user_id)
        empty = RevisionRequest(
            enquiry_id=snap.enquiry_id, expected_revision=1,
            corrections=[ItemCorrection(item_id=uuid4())], reason="noop",
        )
        with self.assertRaises(PartsIQError) as ctx:
            await correct_extraction(owner, F38Request(change=empty), repo=FakeRevisionRepo(snap))
        self.assertEqual(ctx.exception.http_status, 422)

    async def test_stale_revision_rejected(self):
        owner = _actor()
        snap = _snapshot(owner.user_id, revision=3)
        with self.assertRaises(PartsIQError) as ctx:
            await correct_extraction(
                owner, F38Request(change=_change(snap.enquiry_id, revision=1)), repo=FakeRevisionRepo(snap)
            )
        self.assertEqual(ctx.exception.http_status, 409)

    async def test_foreign_actor_denied(self):
        snap = _snapshot(uuid4())  # owned by someone else
        with self.assertRaises(PartsIQError) as ctx:
            await correct_extraction(
                _actor(), F38Request(change=_change(snap.enquiry_id)), repo=FakeRevisionRepo(snap)
            )
        self.assertEqual(ctx.exception.http_status, 404)

    async def test_result_claiming_approval_is_refused(self):
        owner = _actor()
        snap = _snapshot(owner.user_id)
        repo = FakeRevisionRepo(snap, result_status="approved")  # a violation
        with self.assertRaises(PartsIQError) as ctx:
            await correct_extraction(owner, F38Request(change=_change(snap.enquiry_id)), repo=repo)
        self.assertEqual(ctx.exception.http_status, 409)

    async def test_correction_schema_cannot_invent_candidate_facts(self):
        fields = set(ItemCorrection.model_fields)
        for forbidden in ("part_id", "selected_part_id", "configuration_id", "status"):
            self.assertNotIn(forbidden, fields)

    async def test_dependency_failure_propagates(self):
        repo = FakeRevisionRepo(None, raises=PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="db down"))
        with self.assertRaises(PartsIQError) as ctx:
            await correct_extraction(_actor(), F38Request(change=_change(uuid4())), repo=repo)
        self.assertEqual(ctx.exception.code, "DEPENDENCY_UNAVAILABLE")


class ResetDerivedState(unittest.TestCase):
    def test_reset_clears_draft_verification_and_reenters_intake(self):
        item = ItemState(
            id=uuid4(), request=ItemInput(description="a", quantity=Decimal("1"),
                                          source_message_id=uuid4(), source_start=0, source_end=1),
            configuration_id=100, candidate_part_ids=[10], selected_part_id=10, status="ready",
        )
        state = EnquiryState(
            enquiry_id=uuid4(), revision=2, session_generation=None, catalogue_version_id=uuid4(),
            items=[item], step_count=3, pending_question="q", draft_id=uuid4(),
            verification_id=uuid4(), phase="drafted",
        )
        reset = reset_derived_state(state)
        self.assertIsNone(reset.draft_id)
        self.assertIsNone(reset.verification_id)
        self.assertIsNone(reset.pending_question)
        self.assertEqual(reset.phase, "intake")


if __name__ == "__main__":
    unittest.main(verbosity=2)
