"""Acceptance tests for prompt 17 — approved enquiry PDF (foundation gate).

Offline: render_export_html is pure (trusted Jinja template, autoescape); export_enquiry is
driven with a fake Storage/export store and a fake HTML->PDF renderer that returns a real
pypdf-built PDF, so the export pipeline (approved-only gate, hash, storage key, persist) is
exercised without Chromium. The live Playwright/Chromium browser is BLOCKED (binary not
installed). Covers F61.
"""
from __future__ import annotations

import io
import sys
import unittest
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "partsiq_common"))
sys.path.insert(0, str(REPO_ROOT / "services" / "worker"))

from pypdf import PdfReader, PdfWriter  # noqa: E402

from app.jobs.export_pdf import EXPORT_BUCKET, export_enquiry, render_export_html  # noqa: E402
from partsiq_common.contracts import (  # noqa: E402
    Allocation,
    ApprovedSnapshot,
    ExportRequest,
    JobLease,
    VerifiedFacts,
    VerifiedItem,
)
from partsiq_common.errors import PartsIQError  # noqa: E402

WHEN = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _facts(enquiry_id, *, name_en="fuel filter", name_ar="فلتر وقود"):
    return VerifiedFacts(
        enquiry_id=enquiry_id, revision=1, catalogue_version_id=uuid4(),
        items=[VerifiedItem(
            item_id=uuid4(), configuration_id=100, part_id=10, part_number="VP-FF-10",
            name_en=name_en, name_ar=name_ar, requested_quantity=Decimal("2"),
            allocations=[Allocation(warehouse_id=1, quantity=Decimal("2"), transfer_days=2, stock_updated_at=WHEN)],
            shortage=Decimal("0"), source_reference="SYNTH-CA-PB-CA-110 rev 1, section FILTERS", evidence_id=uuid4(),
        )],
    )


def _snapshot(enquiry_id, *, locale="en", reply="<div class='reply'>Hello</div>"):
    return ApprovedSnapshot(
        decision_id=uuid4(), approved_at=WHEN, locale=locale, facts=_facts(enquiry_id),
        reply=reply, synthetic=True,
    )


def _real_pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


class RenderHtml(unittest.TestCase):
    def test_includes_watermark_logo_references_and_estimate(self):
        html = render_export_html(_snapshot(uuid4()))
        self.assertIn("SYNTHETIC DEMO", html)
        self.assertIn("logo-original.png", html)
        self.assertIn("VP-FF-10", html)                               # verified selection
        self.assertIn("SYNTH-CA-PB-CA-110 rev 1, section FILTERS", html)  # reference/citation
        self.assertIn("not guaranteed", html)

    def test_no_price_or_quotation_wording(self):
        import re

        html = render_export_html(_snapshot(uuid4())).lower()
        for word in ("price", "quotation", "$"):
            self.assertNotIn(word, html)
        for currency in (r"\bsar\b", r"\busd\b"):  # whole-word, so font names don't false-match
            self.assertIsNone(re.search(currency, html))

    def test_arabic_is_rtl(self):
        html = render_export_html(_snapshot(uuid4(), locale="ar"))
        self.assertIn('dir="rtl"', html)
        self.assertIn('<bdi dir="ltr"', html)  # identifiers isolated LTR

    def test_user_html_in_names_is_escaped(self):
        # The reply is trusted/pre-escaped; dynamic names are autoescaped by Jinja.
        snap = ApprovedSnapshot(
            decision_id=uuid4(), approved_at=WHEN, locale="en",
            facts=_facts(uuid4(), name_en="<script>x</script>"), reply="<p>ok</p>", synthetic=True,
        )
        html2 = render_export_html(snap)
        self.assertNotIn("<script>x</script>", html2)


class FakeExportStore:
    def __init__(self, snapshot):
        self._snapshot = snapshot
        self.uploaded = None
        self.persisted = None

    async def load_approved(self, enquiry_id, revision, decision_id):
        return self._snapshot

    async def upload(self, bucket, object_key, data):
        self.uploaded = (bucket, object_key, data)

    async def persist_export(self, job, request, storage_key, sha256):
        self.persisted = (storage_key, sha256)
        return uuid4()


class FakeStoreNoApproval:
    async def load_approved(self, enquiry_id, revision, decision_id):
        return None

    async def upload(self, bucket, object_key, data):  # pragma: no cover
        raise AssertionError("must not upload without an approved snapshot")

    async def persist_export(self, job, request, storage_key, sha256):  # pragma: no cover
        raise AssertionError


def _job():
    return JobLease(id=uuid4(), kind="export_pdf", enquiry_id=uuid4(), revision=1, session_generation=None,
                    lease_token=uuid4(), expires_at=WHEN + timedelta(seconds=45), attempt=1, payload={})


async def _render_pdf(html):
    return _real_pdf_bytes()


class ExportEnquiry(unittest.IsolatedAsyncioTestCase):
    async def test_exports_approved_and_hashes_output(self):
        enquiry = uuid4()
        store = FakeExportStore(_snapshot(enquiry))
        request = ExportRequest(enquiry_id=enquiry, revision=1, decision_id=uuid4())
        result = await export_enquiry(_job(), request, store=store, render_pdf=_render_pdf)
        self.assertEqual(store.uploaded[0], EXPORT_BUCKET)
        self.assertTrue(result.storage_key.endswith(f"{result.sha256}.pdf"))
        self.assertRegex(result.sha256, r"^[a-f0-9]{64}$")
        # The uploaded bytes are a valid, single-page PDF (pypdf).
        reader = PdfReader(io.BytesIO(store.uploaded[2]))
        self.assertEqual(len(reader.pages), 1)

    async def test_unapproved_or_stale_revision_rejected(self):
        request = ExportRequest(enquiry_id=uuid4(), revision=1, decision_id=uuid4())
        with self.assertRaises(PartsIQError) as ctx:
            await export_enquiry(_job(), request, store=FakeStoreNoApproval(), render_pdf=_render_pdf)
        self.assertEqual(ctx.exception.code, "CONFLICT")


if __name__ == "__main__":
    unittest.main(verbosity=2)
