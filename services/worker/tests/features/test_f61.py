"""F61 Enquiry PDF — export the approved revision only; exclude notes/secrets; no prices.

Exercises the worker export job: render_export_html contains the watermark/estimate and no
price/quotation wording or staff-note/secret payload, and export_enquiry refuses anything
but an approved immutable revision.
"""
from __future__ import annotations

import re
import unittest
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.jobs.export_pdf import export_enquiry, render_export_html
from partsiq_common.contracts import (
    Allocation,
    ApprovedSnapshot,
    ExportRequest,
    JobLease,
    VerifiedFacts,
    VerifiedItem,
)
from partsiq_common.errors import PartsIQError

WHEN = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _snapshot(locale="en"):
    facts = VerifiedFacts(
        enquiry_id=uuid4(), revision=1, catalogue_version_id=uuid4(),
        items=[VerifiedItem(
            item_id=uuid4(), configuration_id=100, part_id=10, part_number="VP-FF-10",
            name_en="fuel filter", name_ar="فلتر وقود", requested_quantity=Decimal("2"),
            allocations=[Allocation(warehouse_id=1, quantity=Decimal("2"), transfer_days=2, stock_updated_at=WHEN)],
            shortage=Decimal("0"), source_reference="SYNTH-CA-PB-CA-110 rev 1, section FILTERS", evidence_id=uuid4(),
        )],
    )
    return ApprovedSnapshot(decision_id=uuid4(), approved_at=WHEN, locale=locale, facts=facts,
                            reply="<div class='reply'>Hello</div>", synthetic=True)


def _job():
    return JobLease(id=uuid4(), kind="export_pdf", enquiry_id=uuid4(), revision=1, session_generation=None,
                    lease_token=uuid4(), expires_at=WHEN + timedelta(seconds=45), attempt=1, payload={})


class FakeStore:
    def __init__(self, snapshot):
        self._snapshot = snapshot
        self.uploaded = None

    async def load_approved(self, enquiry_id, revision, decision_id):
        return self._snapshot

    async def upload(self, bucket, object_key, data):
        self.uploaded = object_key

    async def persist_export(self, job, request, storage_key, sha256):
        return uuid4()


class NoApprovalStore:
    async def load_approved(self, enquiry_id, revision, decision_id):
        return None

    async def upload(self, *a):  # pragma: no cover
        raise AssertionError

    async def persist_export(self, *a):  # pragma: no cover
        raise AssertionError


async def _render_pdf(html):
    return b"%PDF-1.4 fake"


class EnquiryPdf(unittest.IsolatedAsyncioTestCase):
    def test_html_excludes_prices_and_notes(self):
        html = render_export_html(_snapshot()).lower()
        for banned in ("price", "quotation", "$", "internal note"):
            self.assertNotIn(banned, html)
        for currency in (r"\bsar\b", r"\busd\b"):
            self.assertIsNone(re.search(currency, html))
        self.assertIn("synthetic demo", html)

    async def test_exports_approved_revision(self):  # success
        store = FakeStore(_snapshot())
        result = await export_enquiry(_job(), ExportRequest(enquiry_id=uuid4(), revision=1, decision_id=uuid4()),
                                      store=store, render_pdf=_render_pdf)
        self.assertRegex(result.sha256, r"^[a-f0-9]{64}$")
        self.assertIsNotNone(store.uploaded)

    async def test_unapproved_or_stale_revision_rejected(self):  # stale-revision/invalid
        with self.assertRaises(PartsIQError) as ctx:
            await export_enquiry(_job(), ExportRequest(enquiry_id=uuid4(), revision=1, decision_id=uuid4()),
                                 store=NoApprovalStore(), render_pdf=_render_pdf)
        self.assertEqual(ctx.exception.code, "CONFLICT")


if __name__ == "__main__":
    unittest.main(verbosity=2)
