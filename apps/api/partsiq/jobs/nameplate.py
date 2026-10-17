"""The ``nameplate`` background-job handler (prompt 16 — F14).

Ported and consolidated from ``services/worker/app/jobs/nameplate.py`` (the job-orchestration
half) onto the single ``partsiq`` package. The worker claims a durable ``jobs`` row, hands the
resulting :class:`JobLease` here, and this handler:

1. loads the TRUSTED job context from the lease payload (the attachment object key + media
   type the enquiry's own upload wrote — never a user- or model-supplied table id);
2. downloads the private, already-validated image through the injected storage port;
3. calls :func:`partsiq.ai.vision.read_nameplate` to extract model_text/serial_text/issues
   with confirmation forced on;
4. persists the extraction and appends an ``ocr_completed`` workflow event UNDER THE LEASE,
   fenced by :func:`partsiq.jobs.repository.finish_job` — the result is committed only while
   the lease token, the enquiry revision and the demo generation still match. A late result
   from a superseded revision (F52) or an old demo generation (F05) is DISCARDED, never
   written over current data.

External work (storage fetch + the paid vision call) happens BEFORE the fenced commit and
outside any enquiry row lock (prompt 16 step: do not hold a row lock across network work). A
provider/budget failure propagates as a recoverable :class:`PartsIQError` so the job is
retried / surfaced as a recoverable status rather than committing a fabricated extraction.

The storage, persistence (job store) and vision client are all injected, so the handler is
unit-testable offline; the live Supabase fetch, OpenAI vision call and asyncpg persistence are
BLOCKED here. Registration with the dispatcher happens via
:func:`partsiq.jobs.handlers.register_handler` at import time.
"""
from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from partsiq.ai.vision import read_nameplate
from partsiq.core.contracts import JobLease, JobResult, NameplateResult
from partsiq.core.errors import PartsIQError
from partsiq.jobs.handlers import register_handler
from partsiq.jobs.repository import JobStore, finish_job

JOB_KIND = "nameplate"


class ImageSource(Protocol):
    """Injected private-image fetch. A Supabase Storage download at runtime, fake in tests."""

    async def download(self, object_key: str, media_type: str) -> bytes:
        """Return the raw bytes of the validated private upload at ``object_key``."""
        ...


class ExtractionSink(Protocol):
    """Injected persistence for the extraction + ``ocr_completed`` workflow event.

    The live adapter writes the ``extractions`` row and appends the workflow event in ONE
    transaction. It is invoked only after :func:`finish_job` has accepted the lease fence, so
    a superseded or stale result is never persisted.
    """

    async def save_extraction(
        self, lease: JobLease, extraction: NameplateResult
    ) -> UUID:
        """Persist the extraction + ``ocr_completed`` event; return the extraction id."""
        ...


def _object_key(lease: JobLease) -> str:
    """Read the trusted private object key from the lease payload (never user-supplied)."""
    raw = lease.payload.get("object_key")
    if raw is None or not str(raw).strip():
        raise PartsIQError(
            "MALFORMED_REQUEST", internal_detail="nameplate job missing object_key"
        )
    return str(raw)


def _media_type(lease: JobLease) -> str:
    """Read the declared media type from the lease payload (defaults to JPEG)."""
    return str(lease.payload.get("media_type") or "image/jpeg")


async def run_nameplate_job(
    lease: JobLease,
    *,
    images: ImageSource,
    sink: ExtractionSink,
    store: JobStore,
    client: Any | None = None,
    allow_live: bool = False,
) -> JobResult:
    """Run one nameplate OCR job end to end under its lease.

    Returns a terminal :class:`JobResult`. The extraction is only persisted when the lease
    fence still holds; if ``finish_job`` rejects the commit (stale revision / old generation /
    expired lease) nothing is written and the result is ``cancelled`` so the current data is
    untouched.
    """
    object_key = _object_key(lease)
    media_type = _media_type(lease)

    # External work first, OUTSIDE any enquiry row lock (prompt 16: no network under a lock).
    image = await images.download(object_key, media_type)
    extraction = await read_nameplate(lease, image, client=client, allow_live=allow_live)

    # Fence the commit by the lease: a newer revision (F52) or a bumped demo generation (F05)
    # must NOT be overwritten by this late OCR result.
    committed = await finish_job(
        lease, JobResult(status="succeeded", result_id=None, error_code=None), store=store
    )
    if not committed:
        # The enquiry moved on (or the lease was lost): discard, never write over current data.
        return JobResult(status="cancelled", result_id=None, error_code="STALE_REVISION")

    # The lease is still authoritative: persist the extraction + ocr_completed event.
    extraction_id = await sink.save_extraction(lease, extraction)
    return JobResult(status="succeeded", result_id=extraction_id, error_code=None)


# Register this handler with the dispatcher at import time (prompt 15 allowlist). The worker
# imports this module at startup so the "nameplate" kind becomes dispatchable.
register_handler(JOB_KIND, run_nameplate_job)


__all__ = ["JOB_KIND", "ExtractionSink", "ImageSource", "run_nameplate_job"]
