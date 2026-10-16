"""Worker-side private storage: the only holder of the Storage admin credential.

The worker uses SUPABASE_STORAGE_KEY purely for authorized object operations —
signing downloads, writing evidence/exports, and cleanup. It is NEVER used as a
database REST bypass (CONSTRAINTS.md rule 12, ADR-014).

A download is signed only for a TYPED resource id that the gateway has already
authorized; the object key is resolved from the database by a caller-supplied
resolver, so an arbitrary key can never be signed. Signed links live 60 seconds.

Imports only partsiq_common + stdlib (the `app` package name collides across services).
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol
from uuid import UUID

from partsiq_common.contracts import DownloadRequest
from partsiq_common.errors import PartsIQError

SIGNED_URL_TTL_SECONDS = 60

# Which private bucket backs each download resource type.
BUCKET_FOR_RESOURCE: dict[str, str] = {
    "attachment": "nameplates",
    "evidence": "catalogue-evidence",
    "export": "exports",
}

# Resolver: typed (resource_type, resource_id) -> concrete object key, from the DB.
KeyResolver = Callable[[str, UUID], Awaitable[str]]


class StorageAdmin(Protocol):
    """Minimal Storage-admin surface. Deliberately has no table/REST access."""

    async def create_signed_download_url(self, bucket: str, object_key: str, ttl_seconds: int) -> str: ...

    async def remove(self, bucket: str, object_key: str) -> None: ...


async def sign_download(
    request: DownloadRequest,
    ttl_seconds: int = SIGNED_URL_TTL_SECONDS,
    *,
    backend: StorageAdmin,
    resolve_key: KeyResolver,
) -> str:
    """Resolve a typed resource to its object key and return a short-lived signed URL."""
    bucket = BUCKET_FOR_RESOURCE.get(request.resource_type)
    if bucket is None:
        raise PartsIQError("MALFORMED_REQUEST", internal_detail="unknown resource type")
    object_key = await resolve_key(request.resource_type, request.resource_id)
    if not object_key:
        raise PartsIQError("NOT_FOUND", internal_detail="object not found for resource")
    return await backend.create_signed_download_url(bucket, object_key, ttl_seconds)


async def remove_object(bucket: str, object_key: str, *, backend: StorageAdmin) -> None:
    """Delete a private object (asynchronous cleanup; not a cross-system atomic delete)."""
    if bucket not in set(BUCKET_FOR_RESOURCE.values()) | {"imports"}:
        raise PartsIQError("MALFORMED_REQUEST", internal_detail="unknown bucket")
    await backend.remove(bucket, object_key)
