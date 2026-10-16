"""Attachment confirmation: validate the real uploaded bytes before marking validated.

Contract: ``async def confirm_upload(actor, attachment_id) -> AttachmentView``.

Rules (prompt 08, F13):
  * The object path was generated server-side at upload time; confirmation fetches the
    ACTUAL bytes and checks the magic type against the declared MIME before accepting.
  * A nonexistent or foreign attachment is 404. A duplicate confirmation is idempotent
    (returns the already-resolved status, never re-processes).
  * Invalid content is marked ``rejected`` with a safe error code, not ``validated``.

The decoded-pixel cap / EXIF strip runs in the worker before OCR (prompt 16); here we
enforce existence, ownership, MIME magic and idempotency. Byte fetch + persistence are
injected so the flow is testable without Storage or a database.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.storage import validate_magic
from partsiq_common.contracts import ActorContext, AttachmentView
from partsiq_common.errors import PartsIQError


@dataclass(frozen=True, slots=True)
class PendingAttachment:
    attachment_id: UUID
    media_type: str
    status: str  # pending | validated | rejected | deleted
    error_code: str | None = None


class UploadRepo(Protocol):
    async def get_attachment(self, actor: ActorContext, attachment_id: UUID) -> PendingAttachment | None: ...

    async def mark_validated(self, attachment_id: UUID) -> AttachmentView: ...

    async def mark_rejected(self, attachment_id: UUID, error_code: str) -> AttachmentView: ...


# Fetches the stored object bytes for an attachment (gateway asks the worker/storage).
ByteFetcher = Callable[[UUID], Awaitable[bytes]]


async def confirm_upload(
    actor: ActorContext, attachment_id: UUID, *, repo: UploadRepo, fetch_bytes: ByteFetcher
) -> AttachmentView:
    attachment = await repo.get_attachment(actor, attachment_id)
    if attachment is None:
        raise PartsIQError("NOT_FOUND", internal_detail="attachment not found")
    # Duplicate confirmation is idempotent: return the already-resolved state.
    if attachment.status in ("validated", "rejected", "deleted"):
        return AttachmentView(id=attachment.attachment_id, status=attachment.status, error_code=attachment.error_code)

    data = await fetch_bytes(attachment_id)
    if not validate_magic(data, attachment.media_type):
        return await repo.mark_rejected(attachment_id, "UNSUPPORTED_MEDIA_TYPE")
    return await repo.mark_validated(attachment_id)
