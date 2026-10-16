"""Approved-enquiry PDF export (prompt 17 — F61).

Contracts:
    async def export_enquiry(job: JobLease, request: ExportRequest) -> ExportResult
    def render_export_html(snapshot: ApprovedSnapshot) -> str

Only an approved, immutable revision is exported — a live draft or a stale/unapproved
revision is refused. render_export_html fills a TRUSTED, code-owned Jinja template with
autoescape on (no model-authored template is ever evaluated); the only pre-rendered markup
is the reply, which the code-owned reply renderer already escaped. Arabic renders RTL with
identifiers isolated LTR, long names wrap rather than clip, the synthetic-demo watermark and
the non-guaranteed-estimate note are always present, and no price/quotation wording or staff
note/secret is included. The HTML→PDF step (Chromium via Playwright, with external requests,
JavaScript and arbitrary file access disabled) and Storage upload are injected ports; the
live Playwright/Chromium browser is BLOCKED here (binary not installed).
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol
from uuid import UUID

from jinja2 import Environment, FileSystemLoader, select_autoescape

from partsiq_common.contracts import ApprovedSnapshot, ExportRequest, ExportResult, JobLease
from partsiq_common.errors import PartsIQError

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
_ASSET_DIR = Path(__file__).resolve().parent.parent / "static" / "brand"
EXPORT_BUCKET = "exports"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)


def render_export_html(snapshot: ApprovedSnapshot) -> str:
    """Render the trusted export template from the approved snapshot (pure; no I/O beyond the template)."""
    template = _env.get_template("enquiry_summary.html")
    return template.render(
        locale=snapshot.locale,
        facts=snapshot.facts,
        reply=snapshot.reply,
        synthetic=snapshot.synthetic,
        asset_dir=str(_ASSET_DIR),
    )


class HtmlToPdf(Protocol):
    async def __call__(self, html: str) -> bytes: ...


class ExportStore(Protocol):
    async def load_approved(
        self, enquiry_id: UUID, revision: int, decision_id: UUID
    ) -> ApprovedSnapshot | None: ...

    async def upload(self, bucket: str, object_key: str, data: bytes) -> None: ...

    async def persist_export(
        self, job: JobLease, request: ExportRequest, storage_key: str, sha256: str
    ) -> UUID: ...


async def export_enquiry(
    job: JobLease,
    request: ExportRequest,
    *,
    store: ExportStore,
    render_pdf: HtmlToPdf,
) -> ExportResult:
    snapshot = await store.load_approved(request.enquiry_id, request.revision, request.decision_id)
    if snapshot is None:
        # A live draft or a stale/unapproved revision has no immutable approved snapshot.
        raise PartsIQError("CONFLICT", internal_detail="no approved immutable revision to export")

    html = render_export_html(snapshot)
    pdf = await render_pdf(html)
    sha256 = hashlib.sha256(pdf).hexdigest()
    storage_key = f"{request.enquiry_id}/{request.revision}/{sha256}.pdf"
    await store.upload(EXPORT_BUCKET, storage_key, pdf)
    export_id = await store.persist_export(job, request, storage_key, sha256)
    return ExportResult(export_id=export_id, storage_key=storage_key, sha256=sha256)
