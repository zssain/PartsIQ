"""F65 Correction feedback — curate a REVIEWED correction into an anonymized eval case.

Admin only; an unreviewed correction cannot become ground truth; duplicate source/case id
rejected; the exported fixture carries only the label + provenance, never private text.
"""
from __future__ import annotations

import unittest
from uuid import uuid4

from app.features.f65_correction_feedback import (
    CorrectionRecord,
    CorrectionSummary,
    EvalCaseExport,
    F65Request,
    curate_correction,
    list_corrections,
)
from partsiq_common.contracts import ActorContext
from partsiq_common.errors import PartsIQError


def _admin():
    return ActorContext(user_id=uuid4(), request_id=uuid4(), roles=["admin"])


def _reviewer():
    return ActorContext(user_id=uuid4(), request_id=uuid4(), roles=["reviewer"])


class FakeFeedbackRepo:
    def __init__(self, record=None, *, existing_cases=(), curated_sources=(), raises=None):
        self._record = record
        self._cases = set(existing_cases)
        self._curated = set(curated_sources)
        self._raises = raises
        self.saved: EvalCaseExport | None = None

    async def list_authorized(self, actor):
        return [CorrectionSummary(correction_id=uuid4(), before="VP-9", after="VP-10", reviewed=True, source_revision=2)]

    async def load_correction(self, actor, correction_id):
        if self._raises is not None:
            raise self._raises
        return self._record

    async def case_exists(self, case_id):
        return case_id in self._cases

    async def source_already_curated(self, correction_id):
        return correction_id in self._curated

    async def save_eval_case(self, case):
        self.saved = case


def _record(reviewed=True, revision=2):
    return CorrectionRecord(
        correction_id=uuid4(), reviewed=reviewed, source_revision=revision,
        before="fuel filtr", after="fuel filter", private_text="customer: my email is a@b.com",
    )


def _req(correction_id, case_id="case-001", expected="compatible:VP-10"):
    return F65Request(correction_id=correction_id, case_id=case_id, approved_expected=expected)


class CurateCorrection(unittest.IsolatedAsyncioTestCase):
    async def test_admin_curates_reviewed_correction(self):
        admin = _admin()
        rec = _record()
        repo = FakeFeedbackRepo(rec)
        result = await curate_correction(admin, _req(rec.correction_id), repo=repo)
        self.assertEqual(result.source_revision, 2)
        self.assertEqual(result.approved_by, admin.user_id)
        self.assertEqual(result.case_id, "case-001")

    async def test_exported_case_excludes_private_text(self):
        rec = _record()
        repo = FakeFeedbackRepo(rec)
        await curate_correction(_admin(), _req(rec.correction_id), repo=repo)
        self.assertIsInstance(repo.saved, EvalCaseExport)
        self.assertFalse(hasattr(repo.saved, "private_text"))
        self.assertNotIn("private_text", repo.saved.__dataclass_fields__)

    async def test_non_admin_forbidden(self):
        rec = _record()
        with self.assertRaises(PartsIQError) as ctx:
            await curate_correction(_reviewer(), _req(rec.correction_id), repo=FakeFeedbackRepo(rec))
        self.assertEqual(ctx.exception.http_status, 403)

    async def test_unreviewed_cannot_become_ground_truth(self):
        rec = _record(reviewed=False)
        with self.assertRaises(PartsIQError) as ctx:
            await curate_correction(_admin(), _req(rec.correction_id), repo=FakeFeedbackRepo(rec))
        self.assertEqual(ctx.exception.http_status, 409)

    async def test_duplicate_source_rejected(self):
        rec = _record()
        repo = FakeFeedbackRepo(rec, curated_sources={rec.correction_id})
        with self.assertRaises(PartsIQError) as ctx:
            await curate_correction(_admin(), _req(rec.correction_id), repo=repo)
        self.assertEqual(ctx.exception.http_status, 409)

    async def test_duplicate_case_id_rejected(self):
        rec = _record()
        repo = FakeFeedbackRepo(rec, existing_cases={"case-001"})
        with self.assertRaises(PartsIQError) as ctx:
            await curate_correction(_admin(), _req(rec.correction_id, case_id="case-001"), repo=repo)
        self.assertEqual(ctx.exception.http_status, 409)

    async def test_empty_label_rejected(self):
        rec = _record()
        with self.assertRaises(PartsIQError) as ctx:
            await curate_correction(_admin(), _req(rec.correction_id, expected="   "), repo=FakeFeedbackRepo(rec))
        self.assertEqual(ctx.exception.http_status, 422)

    async def test_missing_correction_not_found(self):
        with self.assertRaises(PartsIQError) as ctx:
            await curate_correction(_admin(), _req(uuid4()), repo=FakeFeedbackRepo(None))
        self.assertEqual(ctx.exception.http_status, 404)

    async def test_dependency_failure_propagates(self):
        repo = FakeFeedbackRepo(None, raises=PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="down"))
        with self.assertRaises(PartsIQError) as ctx:
            await curate_correction(_admin(), _req(uuid4()), repo=repo)
        self.assertEqual(ctx.exception.code, "DEPENDENCY_UNAVAILABLE")


class ListCorrections(unittest.IsolatedAsyncioTestCase):
    async def test_lists_before_after(self):
        listed = await list_corrections(_admin(), repo=FakeFeedbackRepo(_record()))
        self.assertEqual(listed[0].before, "VP-9")
        self.assertEqual(listed[0].after, "VP-10")


if __name__ == "__main__":
    unittest.main(verbosity=2)
