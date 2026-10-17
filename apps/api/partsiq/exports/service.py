"""Approved bilingual PDF export service + ``export_pdf`` job handler (prompt 17 — F61).

Ported and consolidated from the legacy worker ``services/worker/app/jobs/export_pdf.py``
(``export_enquiry``) onto the single ``partsiq`` package. There is no separate worker service;
the worker runs the SAME package and dispatches this handler by its registered ``export_pdf``
kind (``partsiq.jobs.handlers``).

Flow (F61, CONSTRAINTS rules 1, 11, 14):

1. Load the APPROVED, IMMUTABLE snapshot for ``(enquiry_id, revision, decision_id)`` through an
   injected loader. A live draft, a stale/unapproved revision or a changed decision has NO
   immutable approved snapshot, so the loader returns ``None`` and the export is REFUSED with a
   ``CONFLICT`` — nothing is ever rendered, uploaded or persisted.
2. Render the trusted template (``render_export_html``) — autoescaped, bilingual/RTL, with the
   synthetic-demo watermark and the non-guaranteed-estimate note, and with no price/quotation
   wording or staff note/secret.
3. Rasterise HTML→PDF through an INJECTED port. The live Chromium/Playwright browser is a
   deferred/BLOCKED binary here, so the port is injected (a deterministic fake offline); the
   live render renders A4 with print backgrounds and external requests/JS/file access denied.
4. Hash the exact PDF bytes (sha256) and derive a server-chosen, enquiry/revision-scoped object
   key. The customer never supplies the key.
5. Upload the private object to the EXPORTS bucket via ``partsiq.storage``.
6. Persist the export record and commit it UNDER THE LEASE: ``finish_job`` only lands the result
   while the lease token, the enquiry revision (F52) and the demo generation (F05) all still
   match. If the lease was lost or the work was superseded, the result is DISCARDED and the
   export is not reported as applied.

Network/browser work (render + upload) happens BEFORE the fenced ``finish_job`` commit so no
external call is made while holding the row lock (ARCHITECTURE: separate external work from
final fenced persistence). Keys, signed URLs and provider responses never enter a log or error.
"""
from __future__ import annotations

import hashlib
import logging
from collections.abc import Awaitable, Callable
from typing import Protocol
from uuid import UUID

from partsiq.core.contracts import (
    ApprovedSnapshot,
    ExportRequest,
    ExportResult,
    JobLease,
    JobResult,
)
from partsiq.core.errors import PartsIQError
from partsiq.jobs.handlers import register_handler
from partsiq.jobs.repository import JobStore, finish_job
from partsiq.storage.client import BUCKET_EXPORTS

from .render import render_export_html

logger = logging.getLogger("partsiq.exports.service")

EXPORT_JOB_KIND = "export_pdf"


class HtmlToPdf(Protocol):
    """Injected HTML→PDF port. The live Chromium/Playwright browser is BLOCKED here."""

    async def __call__(self, html: str) -> bytes: ...


class ExportUploader(Protocol):
    """Injected private-object uploader for the generated PDF.

    Separate from ``partsiq.storage``'s signed-URL surface (which uploads nothing server-side):
    the PDF is produced here and must be written privately to the exports bucket. The live
    Supabase Storage upload is BLOCKED offline; a fake records the bytes in tests.
    """

    async def upload(self, bucket: str, object_key: str, data: bytes) -> None: ...


# Loads the APPROVED immutable snapshot for a decision, or None when there is none to export.
# Injected so unit tests use a deterministic fake and the live approved-snapshot DB load
# (BLOCKED here) is supplied at runtime. It must refuse anything but an approved snapshot.
ApprovedSnapshotLoader = Callable[[UUID, int, UUID], Awaitable[ApprovedSnapshot | None]]

# Writes the durable export record (export_id, storage_key, sha256) and returns its id.
# Injected; the asyncpg writer is supplied at runtime, a fake in tests.
ExportRecordWriter = Callable[[JobLease, ExportRequest, str, str], Awaitable[UUID]]


def export_object_key(request: ExportRequest, sha256: str) -> str:
    """Server-chosen, content-addressed private key under the enquiry/revision namespace."""
    return f"{request.enquiry_id}/r{request.revision}/{sha256}.pdf"


async def export_enquiry(
    request: ExportRequest,
    *,
    lease: JobLease,
    load_snapshot: ApprovedSnapshotLoader,
    render_pdf: HtmlToPdf,
    uploader: ExportUploader,
    record_writer: ExportRecordWriter,
    job_store: JobStore,
) -> ExportResult:
    """Export an APPROVED immutable revision to a private bilingual PDF (F61).

    Refuses anything but an approved immutable snapshot (``CONFLICT``). Renders, hashes and
    uploads the PDF, then persists the export record and commits it under the lease. A lost or
    superseded lease discards the result rather than reporting a false success.
    """
    snapshot = await load_snapshot(request.enquiry_id, request.revision, request.decision_id)
    if snapshot is None:
        # A live draft or a stale/unapproved/changed-decision revision has no immutable
        # approved snapshot — never render, upload or persist it.
        raise PartsIQError(
            "CONFLICT",
            detail="Only an approved revision can be exported",
            internal_detail="no approved immutable revision to export",
        )

    # External work first, OUTSIDE the fenced commit (no network while holding the row lock).
    html = render_export_html(snapshot)
    pdf = await render_pdf(html)
    sha256 = hashlib.sha256(pdf).hexdigest()
    storage_key = export_object_key(request, sha256)
    await uploader.upload(BUCKET_EXPORTS, storage_key, pdf)

    # Persist the export record, then commit it UNDER THE LEASE. finish_job lands the result
    # only while token + revision (F52) + demo generation (F05) still match.
    export_id = await record_writer(lease, request, storage_key, sha256)
    result = JobResult(status="succeeded", result_id=export_id, error_code=None)
    committed = await finish_job(lease, result, store=job_store)
    if not committed:
        # The lease expired or the revision/generation moved on; the export must not be
        # reported as applied over current data.
        raise PartsIQError(
            "CONFLICT",
            detail="The enquiry changed before the export could be recorded",
            internal_detail="export lease no longer valid at commit",
        )

    logger.info(
        "enquiry export recorded",
        extra={"bucket": BUCKET_EXPORTS, "enquiry_revision": request.revision},
    )
    return ExportResult(export_id=export_id, storage_key=storage_key, sha256=sha256)


async def run_export_job(
    lease: JobLease,
    request: ExportRequest,
    *,
    load_snapshot: ApprovedSnapshotLoader,
    render_pdf: HtmlToPdf,
    uploader: ExportUploader,
    record_writer: ExportRecordWriter,
    job_store: JobStore,
) -> ExportResult:
    """Worker entry point for a claimed ``export_pdf`` lease (handler signature)."""
    return await export_enquiry(
        request,
        lease=lease,
        load_snapshot=load_snapshot,
        render_pdf=render_pdf,
        uploader=uploader,
        record_writer=record_writer,
        job_store=job_store,
    )


def register() -> None:
    """Register the ``export_pdf`` handler on the shared job-kind registry (F51)."""
    register_handler(EXPORT_JOB_KIND, run_export_job)


# Register at import so the worker dispatches export_pdf once this module is imported.
register()


__all__ = [
    "EXPORT_JOB_KIND",
    "ApprovedSnapshotLoader",
    "ExportRecordWriter",
    "ExportUploader",
    "HtmlToPdf",
    "export_enquiry",
    "export_object_key",
    "register",
    "run_export_job",
]
