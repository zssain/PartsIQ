"""Private-upload and signed-download domain service (authorize THEN delegate).

Ported from the legacy gateway/worker storage split into one module behind an injected
:class:`StorageBackend`. The flow enforces the SECURITY.md file controls:

* :func:`create_upload` — the API chooses a UNIQUE, enquiry/revision-scoped PENDING object
  key (a random attachment id, never a caller path) and asks the backend for a signed
  upload URL. The ``UploadRequest`` contract has already bounded the media type and size.
* :func:`sign_download` — resolves a TYPED resource id (``evidence`` / ``export`` /
  ``attachment``) to its bucket + object key through an injected resolver that is scoped to
  the actor. An unknown resource TYPE, or a resource the actor may not read, yields a short,
  safe NOT_FOUND rather than signing an arbitrary key. Path traversal in a resolved key is
  refused before any backend call.

Both tickets expire in ~60 seconds (``SIGNED_URL_TTL_SECONDS``). An already-issued URL stays
valid for its bounded window even if assignment later changes — a deliberate, documented
property of a short-lived signed link, not a leak.

Keys, signed URLs and object paths are never logged or placed in an error detail.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from partsiq.core.contracts import (
    ActorContext,
    DownloadRequest,
    DownloadTicket,
    UploadRequest,
    UploadTicket,
)
from partsiq.core.errors import PartsIQError

from .client import (
    BUCKET_EVIDENCE,
    BUCKET_EXPORTS,
    BUCKET_NAMEPLATES,
    STORAGE_TIMEOUT_SECONDS,
    StorageBackend,
)

logger = logging.getLogger("partsiq.storage.service")

# Signed links live ~60 seconds (SECURITY.md: short-lived signed URLs, bounded validity).
SIGNED_URL_TTL_SECONDS = 60

# Which private bucket backs each typed download resource.
BUCKET_FOR_RESOURCE: dict[str, str] = {
    "attachment": BUCKET_NAMEPLATES,
    "evidence": BUCKET_EVIDENCE,
    "export": BUCKET_EXPORTS,
}

_EXTENSION: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

# Resolver: actor-scoped (resource_type, resource_id) -> concrete object key from the DB.
# Returns None when the resource is unknown OR the actor is not entitled to it; the service
# then raises NOT_FOUND without distinguishing "missing" from "forbidden" to the caller.
KeyResolver = Callable[[ActorContext, str, UUID], Awaitable[str | None]]


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def pending_object_key(enquiry_id: UUID, revision: int, attachment_id: UUID, media_type: str) -> str:
    """Unique PENDING key for an enquiry revision. Server-chosen; never a caller path.

    One attachment id maps to exactly one immutable key, so re-uploads cannot collide and
    an older signed URL can only ever point at its own object.
    """
    extension = _EXTENSION.get(media_type, "")
    return f"{enquiry_id}/r{revision}/{attachment_id}{extension}"


def _rejects_traversal(object_key: str) -> bool:
    """True when a resolved key is safe (no absolute path, no parent/traversal segments)."""
    if not object_key or object_key.startswith("/") or "\\" in object_key:
        return False
    segments = object_key.split("/")
    return ".." not in segments and "" not in segments[1:]


async def create_upload(
    actor: ActorContext,
    command: UploadRequest,
    *,
    backend: StorageBackend,
    ttl_seconds: int = SIGNED_URL_TTL_SECONDS,
) -> UploadTicket:
    """Mint a pending attachment id and a short-lived signed upload URL.

    ``UploadRequest`` already bounds ``media_type`` (image allowlist) and ``size_bytes``
    (<= 10 MiB) via the contract; this function adds the server-chosen unique key and the
    expiry window.
    """
    if command.media_type not in BUCKET_FOR_RESOURCE.values() and command.media_type not in _EXTENSION:
        # Defensive: the contract Literal should already prevent this.
        raise PartsIQError("UNSUPPORTED_MEDIA_TYPE", internal_detail="media type not allowed")

    attachment_id = uuid4()
    object_key = pending_object_key(
        command.enquiry_id, command.expected_revision, attachment_id, command.media_type
    )
    upload_url = await backend.create_signed_upload_url(
        BUCKET_NAMEPLATES, object_key, ttl_seconds
    )
    logger.info(
        "upload ticket issued",
        extra={
            "bucket": BUCKET_NAMEPLATES,
            "ttl_seconds": ttl_seconds,
            "timeout_seconds": STORAGE_TIMEOUT_SECONDS,
        },
    )
    return UploadTicket(
        attachment_id=attachment_id,
        upload_url=upload_url,
        expires_at=_now() + timedelta(seconds=ttl_seconds),
    )


async def sign_download(
    request: DownloadRequest,
    *,
    backend: StorageBackend,
    resolve_key: KeyResolver,
    ttl_seconds: int = SIGNED_URL_TTL_SECONDS,
) -> DownloadTicket:
    """Authorize-then-delegate: resolve a typed resource to a key and sign a 60s URL.

    An unknown resource type, a resource the actor cannot read, or a traversal-shaped key
    all collapse to NOT_FOUND — the service refuses to sign an arbitrary or foreign key.
    """
    bucket = BUCKET_FOR_RESOURCE.get(request.resource_type)
    if bucket is None:
        # The contract Literal should prevent this; treat an unknown type as not found.
        raise PartsIQError("NOT_FOUND", internal_detail="unknown resource type")

    object_key = await resolve_key(request.actor, request.resource_type, request.resource_id)
    if not object_key or not _rejects_traversal(object_key):
        # Unresolved (missing/foreign) or unsafe key — never sign it.
        raise PartsIQError("NOT_FOUND", internal_detail="resource not resolvable for actor")

    url = await backend.create_signed_download_url(bucket, object_key, ttl_seconds)
    logger.info(
        "download ticket issued",
        extra={
            "bucket": bucket,
            "resource_type": request.resource_type,
            "ttl_seconds": ttl_seconds,
        },
    )
    return DownloadTicket(url=url, expires_at=_now() + timedelta(seconds=ttl_seconds))


__all__ = [
    "BUCKET_FOR_RESOURCE",
    "KeyResolver",
    "SIGNED_URL_TTL_SECONDS",
    "create_upload",
    "pending_object_key",
    "sign_download",
]
