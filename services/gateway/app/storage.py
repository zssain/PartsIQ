"""Gateway-side private storage: owner uploads and authorized download signing.

Division of trust (CONSTRAINTS.md rule 12, ADR-014):
  * The gateway signs an UPLOAD with the END USER's Supabase token, so the
    ``nameplates`` RLS policy (owner + pending attachment) authorizes it. The gateway
    never holds the Storage admin credential.
  * For a DOWNLOAD, the gateway first authorizes the request, then asks the worker's
    internal signing handler with a TYPED resource id (resource_type + resource_id) —
    never an arbitrary object key.
  * Signed links live 60 seconds and are stripped from logs.

This module imports only partsiq_common + stdlib so it can be loaded without the rest
of the `app` package (whose name collides across services).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID, uuid4

from partsiq_common.contracts import ActorContext, DownloadRequest, DownloadTicket, UploadRequest, UploadTicket
from partsiq_common.errors import PartsIQError

SIGNED_URL_TTL_SECONDS = 60
UPLOAD_BUCKET = "nameplates"

# media_type -> (file extension, acceptable magic-byte prefixes)
_MEDIA: dict[str, tuple[str, tuple[bytes, ...]]] = {
    "image/jpeg": (".jpg", (b"\xff\xd8\xff",)),
    "image/png": (".png", (b"\x89PNG\r\n\x1a\n",)),
    "image/webp": (".webp", (b"RIFF",)),  # plus 'WEBP' at bytes 8..12, checked below
}


class UploadSigner(Protocol):
    async def create_upload_url(self, bucket: str, object_key: str, ttl_seconds: int) -> str: ...


class WorkerDownloadSigner(Protocol):
    async def sign(self, request: DownloadRequest, ttl_seconds: int) -> str: ...


def object_key_for(enquiry_id: UUID, attachment_id: UUID, media_type: str) -> str:
    """Unique, enquiry-scoped object key. One attachment id -> one immutable key."""
    extension = _MEDIA[media_type][0]
    return f"{enquiry_id}/{attachment_id}{extension}"


def validate_magic(data: bytes, media_type: str) -> bool:
    """Confirm the real bytes match the declared image type (defence vs content spoofing)."""
    if media_type not in _MEDIA:
        return False
    prefixes = _MEDIA[media_type][1]
    if not any(data.startswith(prefix) for prefix in prefixes):
        return False
    if media_type == "image/webp":
        return len(data) >= 12 and data[8:12] == b"WEBP"
    return True


def redact_url_for_log(url: str) -> str:
    """Drop the query string (signature/token) so a signed URL is safe to log."""
    return url.split("?", 1)[0] + "?<redacted>" if "?" in url else url


async def create_upload(
    actor: ActorContext,
    request: UploadRequest,
    *,
    signer: UploadSigner,
) -> UploadTicket:
    """Create a pending-attachment upload ticket for the owner's signed upload.

    Media type and size are already bounded by the UploadRequest contract (10 MiB cap,
    allowed image types). The returned URL expires in 60 seconds.
    """
    if request.media_type not in _MEDIA:
        raise PartsIQError("UNSUPPORTED_MEDIA_TYPE", internal_detail=request.media_type)
    attachment_id = uuid4()
    object_key = object_key_for(request.enquiry_id, attachment_id, request.media_type)
    upload_url = await signer.create_upload_url(UPLOAD_BUCKET, object_key, SIGNED_URL_TTL_SECONDS)
    expires_at = _now() + timedelta(seconds=SIGNED_URL_TTL_SECONDS)
    return UploadTicket(attachment_id=attachment_id, upload_url=upload_url, expires_at=expires_at)


async def sign_download(
    request: DownloadRequest,
    *,
    worker: WorkerDownloadSigner,
) -> DownloadTicket:
    """Authorize-then-delegate: hand a TYPED resource id to the worker signer."""
    if request.resource_type not in ("evidence", "export", "attachment"):
        raise PartsIQError("MALFORMED_REQUEST", internal_detail="unknown resource type")
    url = await worker.sign(request, SIGNED_URL_TTL_SECONDS)
    expires_at = _now() + timedelta(seconds=SIGNED_URL_TTL_SECONDS)
    return DownloadTicket(url=url, expires_at=expires_at)


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


# Re-export for type checkers / callers that pass a concrete backend object.
__all__ = [
    "create_upload",
    "sign_download",
    "object_key_for",
    "validate_magic",
    "redact_url_for_log",
    "SIGNED_URL_TTL_SECONDS",
]
