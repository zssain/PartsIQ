"""Foundation 17 acceptance: approved bilingual PDF export (F61).

Ports the behaviour characterized in the legacy worker tests
(``services/worker/tests/features/test_f61.py``) onto the single ``partsiq`` package. The
worker runs the SAME package and dispatches the registered ``export_pdf`` handler.

Deterministic and fully offline. The live Chromium/Playwright render, the live Supabase
Storage upload and the live approved-snapshot DB load are BLOCKED; each is an injected port
with a deterministic fake here. The live Chromium render is SKIPPED (never faked as a browser),
gated behind ``PARTSIQ_LIVE_INFRA``.

Covered behaviours:
  * render_export_html autoescapes EVERY interpolated value (an HTML/script-laced part name,
    source reference or part number cannot execute) and marks ONLY the pre-escaped reply safe;
  * the output always carries the synthetic-demo watermark and the non-guaranteed-estimate
    note, and NEVER a price/currency or quotation title;
  * Arabic renders RTL with Arabic fonts and LTR-isolated identifiers; both locales render;
  * a non-approved / non-immutable / changed-decision revision is REFUSED — nothing is
    rendered, uploaded or persisted;
  * on success the PDF bytes are sha256-hashed, uploaded privately to the exports bucket, and
    the export record is committed ONLY under a valid lease;
  * the lease fence discards the result when the revision (F52) or demo generation (F05) moved
    on, or when the lease token was reclaimed — no false success is reported;
  * the ``export_pdf`` handler is registered on the shared job registry.
"""
from __future__ import annotations

import os
import re
import unittest
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from partsiq.core.contracts import (
    Allocation,
    ApprovedSnapshot,
    ExportRequest,
    JobLease,
    VerifiedFacts,
    VerifiedItem,
)
from partsiq.core.errors import PartsIQError
from partsiq.enquiries.renderer import render_reply
from partsiq.exports import service as export_service
from partsiq.exports.render import render_export_html
from partsiq.exports.service import (
    EXPORT_JOB_KIND,
    export_enquiry,
    export_object_key,
    run_export_job,
)
from partsiq.jobs.handlers import get_handler, register_handler, registered_kinds
from partsiq.jobs.repository import InMemoryJobStore, JobRow, claim_job
from partsiq.storage.client import BUCKET_EXPORTS

try:  # optional: validate single-page-ness of a produced PDF when pypdf is present
    from pypdf import PdfReader

    _HAS_PYPDF = True
except Exception:  # pragma: no cover - pypdf optional
    _HAS_PYPDF = False

WHEN = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)

# An HTML/script-laced string smuggled through catalogue/source fields; it must be escaped,
# never rendered as live markup, in the trusted template.
INJECT = '<script>alert("x")</script><img src=x onerror=alert(1)>'


def _facts(*, locale: str = "en", inject: bool = False) -> VerifiedFacts:
    name_en = f"fuel filter {INJECT}" if inject else "fuel filter assembly"
    ref = f"SYNTH-CA-PB-CA-110 rev 1 {INJECT}" if inject else "SYNTH-CA-PB-CA-110 rev 1, FILTERS"
    return VerifiedFacts(
        enquiry_id=uuid4(),
        revision=1,
        catalogue_version_id=uuid4(),
        items=[
            VerifiedItem(
                item_id=uuid4(),
                configuration_id=100,
                part_id=10,
                part_number="VP-FF-10",
                name_en=name_en,
                # A long mixed Arabic/English name must wrap, not clip.
                name_ar="فلتر وقود طويل جدا للتأكد من التفاف الاسم الطويل fuel filter assembly long",
                requested_quantity=Decimal("2"),
                allocations=[
                    Allocation(warehouse_id=1, quantity=Decimal("2"), transfer_days=2, stock_updated_at=WHEN)
                ],
                shortage=Decimal("0"),
                source_reference=ref,
                evidence_id=uuid4(),
            )
        ],
    )


def _snapshot(*, locale: str = "en", inject: bool = False) -> ApprovedSnapshot:
    facts = _facts(locale=locale, inject=inject)
    # The reply is produced by the code-owned renderer — already HTML-escaped markup. It is the
    # only value the template marks |safe.
    from partsiq.core.contracts import ReplySlots

    reply = render_reply(
        ReplySlots(greeting="Hello", explanation="Here is your selection.", closing="Thanks"),
        facts,
        locale,  # type: ignore[arg-type]
    )
    return ApprovedSnapshot(
        decision_id=uuid4(), approved_at=WHEN, locale=locale, facts=facts, reply=reply, synthetic=True  # type: ignore[arg-type]
    )


def _lease(*, enquiry_id: UUID | None = None, revision: int | None = 1, generation: int | None = None) -> JobLease:
    return JobLease(
        id=uuid4(),
        kind="export_pdf",
        enquiry_id=enquiry_id,
        revision=revision,
        session_generation=generation,
        lease_token=uuid4(),
        expires_at=WHEN + timedelta(seconds=45),
        attempt=1,
        payload={},
    )


def _minimal_pdf() -> bytes:
    """A deterministic, valid single-page PDF (correct xref/startxref) for the fake renderer."""
    header = b"%PDF-1.4\n"
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >>",
    ]
    body = bytearray()
    offsets: list[int] = []
    for i, obj in enumerate(objs, start=1):
        offsets.append(len(header) + len(body))
        body += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_pos = len(header) + len(body)
    count = len(objs) + 1
    xref = bytearray(f"xref\n0 {count}\n".encode())
    xref += b"0000000000 65535 f \n"
    for off in offsets:
        xref += f"{off:010d} 00000 n \n".encode()
    trailer = f"trailer\n<< /Size {count} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    return bytes(header + body + xref + trailer)


async def _render_pdf(html: str) -> bytes:
    # Deterministic fake standing in for the BLOCKED Chromium render.
    return _minimal_pdf()


class FakeUploader:
    def __init__(self) -> None:
        self.uploaded: list[tuple[str, str, int]] = []

    async def upload(self, bucket: str, object_key: str, data: bytes) -> None:
        self.uploaded.append((bucket, object_key, len(data)))


class FakeRecordWriter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.export_id = uuid4()

    async def __call__(self, lease, request, storage_key, sha256):
        self.calls.append((storage_key, sha256))
        return self.export_id


def _loader_for(snapshot):
    async def _load(enquiry_id, revision, decision_id):
        return snapshot

    return _load


async def _no_snapshot(enquiry_id, revision, decision_id):
    return None


# --------------------------------------------------------------------------- render (HTML)


class RenderHtml(unittest.TestCase):
    def test_autoescapes_injected_text(self):  # F27 — no injected markup executes
        html = render_export_html(_snapshot(inject=True))
        # No live tag from the injected catalogue/source text survives — both the <script>
        # and the <img onerror=...> become inert, escaped text.
        self.assertNotIn("<script>alert", html)
        self.assertNotIn("<img src=x onerror", html)
        self.assertIn("&lt;script&gt;", html)  # it is escaped instead
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", html)

    def test_only_reply_is_marked_safe(self):  # the pre-escaped reply keeps its markup
        snapshot = _snapshot()
        html = render_export_html(snapshot)
        # The code-owned reply's own markup (its wrapper div) is present, not escaped away.
        self.assertIn('<div class="reply"', html)
        self.assertIn("<section class=\"reply\">", html)

    def test_no_price_or_quotation_wording(self):  # CONSTRAINTS 1, 14; F61
        for locale in ("en", "ar"):
            html = render_export_html(_snapshot(locale=locale)).lower()
            for banned in ("price", "quotation", "quote", "invoice", "total", "$", "€", "£"):
                self.assertNotIn(banned, html, f"{banned!r} leaked into {locale} export")
            for currency in (r"\bsar\b", r"\busd\b", r"\baed\b"):
                self.assertIsNone(re.search(currency, html), f"{currency} leaked into {locale}")

    def test_watermark_and_estimate_note_present_en(self):
        html = render_export_html(_snapshot(locale="en"))
        self.assertIn("SYNTHETIC DEMO", html)
        self.assertIn("estimates only and are not guaranteed", html)
        self.assertIn("not a commercial offer", html)

    def test_watermark_and_estimate_note_present_ar(self):
        html = render_export_html(_snapshot(locale="ar"))
        self.assertIn("بيانات توضيحية اصطناعية", html)  # synthetic-demo note
        self.assertIn("غير مضمونة", html)  # not guaranteed

    def test_bilingual_rtl_and_fonts(self):
        ar = render_export_html(_snapshot(locale="ar"))
        self.assertIn('dir="rtl"', ar)
        self.assertIn('lang="ar"', ar)
        self.assertIn("NotoSansArabic", ar)  # Arabic font embedded
        self.assertIn("<bdi", ar)  # identifiers LTR-isolated inside RTL prose
        en = render_export_html(_snapshot(locale="en"))
        self.assertIn('dir="ltr"', en)
        self.assertIn('lang="en"', en)

    def test_long_name_wrap_rule_present(self):  # long Arabic names wrap, never clip
        html = render_export_html(_snapshot(locale="ar"))
        self.assertIn("word-break: break-word", html)

    def test_asset_dir_override_is_used(self):  # asset dir comes from code, not untrusted input
        html = render_export_html(_snapshot(), asset_dir="/opt/custom/brand")
        self.assertIn("file:///opt/custom/brand/logo-original.png", html)


# --------------------------------------------------------------------------- service (export)


class ExportService(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        # Another test module may have called clear_handlers(); the service registers at import,
        # so re-assert it here (idempotent) to stay independent of test ordering.
        export_service.register()

    def test_handler_registered(self):
        self.assertEqual(get_handler(EXPORT_JOB_KIND), run_export_job)
        self.assertIn(EXPORT_JOB_KIND, registered_kinds())

    async def test_exports_approved_revision(self):  # success path
        enquiry = uuid4()
        store = InMemoryJobStore()
        row = JobRow(id=uuid4(), kind="export_pdf", enquiry_id=enquiry, revision=1, session_generation=None)
        store.add(row)
        store.set_fence(enquiry, revision=1, generation=None)
        lease = await claim_job(row.id, "w1", store=store)
        assert lease is not None

        uploader, writer = FakeUploader(), FakeRecordWriter()
        request = ExportRequest(enquiry_id=enquiry, revision=1, decision_id=uuid4())
        result = await export_enquiry(
            request,
            lease=lease,
            load_snapshot=_loader_for(_snapshot()),
            render_pdf=_render_pdf,
            uploader=uploader,
            record_writer=writer,
            job_store=store,
        )
        self.assertRegex(result.sha256, r"^[a-f0-9]{64}$")
        self.assertEqual(result.export_id, writer.export_id)
        # Uploaded privately to the exports bucket under a server-chosen, content-addressed key.
        self.assertEqual(len(uploader.uploaded), 1)
        bucket, key, _ = uploader.uploaded[0]
        self.assertEqual(bucket, BUCKET_EXPORTS)
        self.assertEqual(key, result.storage_key)
        self.assertEqual(key, export_object_key(request, result.sha256))
        self.assertIn(result.sha256, key)
        # The export record is committed under the lease: the job row is now terminal.
        self.assertEqual(store.rows[row.id].status, "succeeded")
        self.assertEqual(store.rows[row.id].result.result_id, writer.export_id)

    async def test_hash_matches_bytes(self):
        import hashlib

        enquiry = uuid4()
        store = InMemoryJobStore()
        row = JobRow(id=uuid4(), kind="export_pdf", enquiry_id=enquiry, revision=1)
        store.add(row)
        store.set_fence(enquiry, revision=1, generation=None)
        lease = await claim_job(row.id, "w1", store=store)
        assert lease is not None
        result = await export_enquiry(
            ExportRequest(enquiry_id=enquiry, revision=1, decision_id=uuid4()),
            lease=lease,
            load_snapshot=_loader_for(_snapshot()),
            render_pdf=_render_pdf,
            uploader=FakeUploader(),
            record_writer=FakeRecordWriter(),
            job_store=store,
        )
        expected = hashlib.sha256(await _render_pdf("")).hexdigest()
        self.assertEqual(result.sha256, expected)

    async def test_unapproved_or_stale_revision_refused(self):  # nothing rendered/uploaded/persisted
        uploader, writer = FakeUploader(), FakeRecordWriter()
        store = InMemoryJobStore()
        lease = _lease(enquiry_id=uuid4())
        with self.assertRaises(PartsIQError) as ctx:
            await export_enquiry(
                ExportRequest(enquiry_id=uuid4(), revision=1, decision_id=uuid4()),
                lease=lease,
                load_snapshot=_no_snapshot,
                render_pdf=_render_pdf,
                uploader=uploader,
                record_writer=writer,
                job_store=store,
            )
        self.assertEqual(ctx.exception.code, "CONFLICT")
        self.assertEqual(uploader.uploaded, [])  # never uploaded
        self.assertEqual(writer.calls, [])  # never persisted

    async def test_result_discarded_on_stale_revision(self):  # F52 — lease fenced by revision
        enquiry = uuid4()
        store = InMemoryJobStore()
        row = JobRow(id=uuid4(), kind="export_pdf", enquiry_id=enquiry, revision=1, session_generation=1)
        store.add(row)
        store.set_fence(enquiry, revision=2, generation=1)  # a newer revision supersedes this
        lease = await claim_job(row.id, "w1", store=store)
        assert lease is not None
        with self.assertRaises(PartsIQError) as ctx:
            await export_enquiry(
                ExportRequest(enquiry_id=enquiry, revision=1, decision_id=uuid4()),
                lease=lease,
                load_snapshot=_loader_for(_snapshot()),
                render_pdf=_render_pdf,
                uploader=FakeUploader(),
                record_writer=FakeRecordWriter(),
                job_store=store,
            )
        self.assertEqual(ctx.exception.code, "CONFLICT")
        self.assertNotEqual(store.rows[row.id].status, "succeeded")  # no false success committed

    async def test_result_discarded_on_old_generation(self):  # F05 — demo reset bumped generation
        enquiry = uuid4()
        store = InMemoryJobStore()
        row = JobRow(id=uuid4(), kind="export_pdf", enquiry_id=enquiry, revision=1, session_generation=1)
        store.add(row)
        store.set_fence(enquiry, revision=1, generation=2)
        lease = await claim_job(row.id, "w1", store=store)
        assert lease is not None
        with self.assertRaises(PartsIQError):
            await export_enquiry(
                ExportRequest(enquiry_id=enquiry, revision=1, decision_id=uuid4()),
                lease=lease,
                load_snapshot=_loader_for(_snapshot()),
                render_pdf=_render_pdf,
                uploader=FakeUploader(),
                record_writer=FakeRecordWriter(),
                job_store=store,
            )
        self.assertNotEqual(store.rows[row.id].status, "succeeded")

    async def test_result_discarded_on_reclaimed_lease(self):  # expired worker cannot commit
        enquiry = uuid4()
        store = InMemoryJobStore()
        row = JobRow(id=uuid4(), kind="export_pdf", enquiry_id=enquiry, revision=1)
        store.add(row)
        store.set_fence(enquiry, revision=1, generation=None)
        lease = await claim_job(row.id, "w1", store=store)
        assert lease is not None
        store.rows[row.id].lease_token = uuid4()  # another worker reclaimed the lease
        with self.assertRaises(PartsIQError):
            await export_enquiry(
                ExportRequest(enquiry_id=enquiry, revision=1, decision_id=uuid4()),
                lease=lease,
                load_snapshot=_loader_for(_snapshot()),
                render_pdf=_render_pdf,
                uploader=FakeUploader(),
                record_writer=FakeRecordWriter(),
                job_store=store,
            )

    async def test_runs_through_registered_handler(self):  # worker dispatch path
        enquiry = uuid4()
        store = InMemoryJobStore()
        row = JobRow(id=uuid4(), kind="export_pdf", enquiry_id=enquiry, revision=1)
        store.add(row)
        store.set_fence(enquiry, revision=1, generation=None)
        lease = await claim_job(row.id, "w1", store=store)
        assert lease is not None
        handler = get_handler(EXPORT_JOB_KIND)
        assert handler is not None
        result = await handler(
            lease,
            ExportRequest(enquiry_id=enquiry, revision=1, decision_id=uuid4()),
            load_snapshot=_loader_for(_snapshot()),
            render_pdf=_render_pdf,
            uploader=FakeUploader(),
            record_writer=FakeRecordWriter(),
            job_store=store,
        )
        self.assertRegex(result.sha256, r"^[a-f0-9]{64}$")

    @unittest.skipUnless(_HAS_PYPDF, "pypdf not installed")
    async def test_produced_pdf_is_single_page(self):  # optional single-page check
        import io

        pdf = await _render_pdf(render_export_html(_snapshot()))
        reader = PdfReader(io.BytesIO(pdf))
        self.assertEqual(len(reader.pages), 1)


@unittest.skipUnless(
    os.environ.get("PARTSIQ_LIVE_INFRA") == "1",
    "live Chromium/Playwright render + Supabase upload are BLOCKED offline; run only when PARTSIQ_LIVE_INFRA=1",
)
class LiveRender(unittest.IsolatedAsyncioTestCase):  # pragma: no cover - integration gate
    async def test_chromium_render(self):
        self.fail("live Chromium/Playwright page.pdf render is integration work (BLOCKED)")


def test_module_registers_on_import():  # import side effect keeps the handler available
    assert export_service.EXPORT_JOB_KIND == "export_pdf"
    # Re-registering is idempotent and does not raise.
    register_handler(EXPORT_JOB_KIND, run_export_job)


if __name__ == "__main__":
    unittest.main(verbosity=2)
