"""Supabase Storage adapter — the single holder of the Storage service-role credential.

Division of trust (SECURITY.md "Database and file controls", ARCHITECTURE section 7,
ADR-014). The Supabase SERVICE-ROLE key is used ONLY here, purely for authorized object
operations against Storage (signing uploads/downloads and cleanup). It is NEVER used as a
database REST bypass: ordinary business queries go through least-privilege LOGIN roles.

The concrete Supabase client is created lazily and only when an operation runs, so this
module imports with no network and no credential requirement (live Storage is BLOCKED in
this environment). Tests inject an in-memory fake that satisfies :class:`StorageBackend`.

Redaction rule (CONSTRAINTS rule 10): keys, JWTs, signed URLs and private object paths
never enter a log line or an error string. Only coarse, non-identifying facts are logged.
"""
from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from partsiq.core.errors import PartsIQError
from partsiq.core.settings import Settings, load_settings

logger = logging.getLogger("partsiq.storage.client")

# The four private buckets defined in spec/sql/005_storage.sql. Nothing here is public.
BUCKET_NAMEPLATES = "nameplates"
BUCKET_EVIDENCE = "catalogue-evidence"
BUCKET_IMPORTS = "imports"
BUCKET_EXPORTS = "exports"
PRIVATE_BUCKETS: frozenset[str] = frozenset(
    {BUCKET_NAMEPLATES, BUCKET_EVIDENCE, BUCKET_IMPORTS, BUCKET_EXPORTS}
)

# Every dependency call is bounded (ARCHITECTURE: explicit bounded timeouts everywhere).
STORAGE_TIMEOUT_SECONDS = 10.0


@runtime_checkable
class StorageBackend(Protocol):
    """Minimal Storage-admin surface. Deliberately has NO table / database REST access.

    Implementations sign URLs and manage objects only. ``object_key`` is always a
    server-chosen key; callers must never pass a user-supplied path (see service.py).
    """

    async def create_signed_upload_url(
        self, bucket: str, object_key: str, ttl_seconds: int
    ) -> str: ...

    async def create_signed_download_url(
        self, bucket: str, object_key: str, ttl_seconds: int
    ) -> str: ...

    async def download(self, bucket: str, object_key: str) -> bytes: ...

    async def remove(self, bucket: str, object_key: str) -> None: ...


def _redact_url(url: str) -> str:
    """Drop the query string (signature/token) so a signed URL is safe to log."""
    if "?" in url:
        return url.split("?", 1)[0] + "?<redacted>"
    return url


class SupabaseStorageBackend:
    """Live Supabase Storage backend. BLOCKED in this environment; constructed lazily.

    The supabase client dependency is imported INSIDE the method, never at module import,
    so importing this module performs no network work and requires no key. When the
    service role key is absent the backend refuses to act rather than signing blindly.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or load_settings()
        self._client: object | None = None

    def _require_client(self) -> object:
        if self._client is not None:
            return self._client
        settings = self._settings
        if not settings.supabase_url or not settings.supabase_service_role_key:
            # Never echo the missing value; report only the bounded, safe fact.
            raise PartsIQError(
                "DEPENDENCY_UNAVAILABLE",
                detail="Storage is not configured",
                internal_detail="supabase storage credentials absent",
            )
        try:
            from supabase import create_client  # type: ignore[attr-defined,import-not-found]
        except ImportError as exc:  # pragma: no cover - supabase not installed offline
            raise PartsIQError(
                "DEPENDENCY_UNAVAILABLE",
                detail="Storage is not configured",
                internal_detail="supabase client unavailable",
            ) from exc
        self._client = create_client(
            settings.supabase_url, settings.supabase_service_role_key
        )
        return self._client

    async def create_signed_upload_url(
        self, bucket: str, object_key: str, ttl_seconds: int
    ) -> str:  # pragma: no cover - live Supabase is BLOCKED here
        client = self._require_client()
        storage = client.storage.from_(bucket)  # type: ignore[attr-defined]
        result = storage.create_signed_upload_url(object_key)
        logger.info("signed upload url issued", extra={"bucket": bucket})
        return str(result["signed_url"])

    async def create_signed_download_url(
        self, bucket: str, object_key: str, ttl_seconds: int
    ) -> str:  # pragma: no cover - live Supabase is BLOCKED here
        client = self._require_client()
        storage = client.storage.from_(bucket)  # type: ignore[attr-defined]
        result = storage.create_signed_url(object_key, ttl_seconds)
        logger.info("signed download url issued", extra={"bucket": bucket})
        return str(result["signedURL"])

    async def download(
        self, bucket: str, object_key: str
    ) -> bytes:  # pragma: no cover - live Supabase is BLOCKED here
        client = self._require_client()
        storage = client.storage.from_(bucket)  # type: ignore[attr-defined]
        return bytes(storage.download(object_key))

    async def remove(
        self, bucket: str, object_key: str
    ) -> None:  # pragma: no cover - live Supabase is BLOCKED here
        client = self._require_client()
        storage = client.storage.from_(bucket)  # type: ignore[attr-defined]
        storage.remove([object_key])
        logger.info("object removed", extra={"bucket": bucket})


__all__ = [
    "BUCKET_EVIDENCE",
    "BUCKET_EXPORTS",
    "BUCKET_IMPORTS",
    "BUCKET_NAMEPLATES",
    "PRIVATE_BUCKETS",
    "STORAGE_TIMEOUT_SECONDS",
    "StorageBackend",
    "SupabaseStorageBackend",
]
