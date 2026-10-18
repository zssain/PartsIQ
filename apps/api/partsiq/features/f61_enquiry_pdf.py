"""F61 Enquiry PDF facade (helpers ``exports.request_pdf`` / ``exports.sign_download``).

A customer exports an APPROVED enquiry as a PDF, then downloads it via a short-lived signed URL.

  * ``request_pdf`` queues a durable export job for a specific approved ``(revision, decision_id)``
    and returns the job handle (202). The export renders only what a human APPROVED — it binds to
    the approval decision, so an unapproved or superseded revision cannot be exported, and no reply
    prose is fabricated. Idempotent on the request ``Idempotency-Key``.
  * ``sign_download`` mints a short-lived signed download URL for a finished export the caller owns
    (200). The PDF bytes live in private storage and are never public; only an owner-scoped signed
    ticket grants access, so a foreign export id is NOT_FOUND.

Both are OWNER access (ownership from the verified actor). Thin adapter over an injected port; the
live export/storage adapter is BLOCKED offline, so the customer gets a clean 503 rather than a
fabricated export or URL.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from partsiq.core.api_models import JobView
from partsiq.core.contracts import ActorContext, DownloadTicket, ExportRequest
from partsiq.core.dependencies import AppContainer
from partsiq.features._ops_ports import require_store


@runtime_checkable
class ExportSource(Protocol):
    """Owner-scoped PDF export port (binds to an approval; private storage)."""

    async def request_pdf(
        self, actor: ActorContext, request: ExportRequest, key: UUID
    ) -> JobView: ...

    async def sign_download(self, actor: ActorContext, export_id: UUID) -> DownloadTicket: ...


async def request_pdf(
    actor: ActorContext,
    request: ExportRequest,
    key: UUID,
    *,
    container: AppContainer,
    source: ExportSource | None = None,
) -> JobView:
    """Queue a PDF export of an APPROVED enquiry revision; idempotent on the key (owner access)."""
    source = source or require_store(container, "exports")
    return await source.request_pdf(actor, request, key)


async def sign_download(
    actor: ActorContext,
    export_id: UUID,
    *,
    container: AppContainer,
    source: ExportSource | None = None,
) -> DownloadTicket:
    """Mint a short-lived signed download URL for a finished export the caller owns (owner access)."""
    source = source or require_store(container, "exports")
    return await source.sign_download(actor, export_id)
