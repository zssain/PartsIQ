"""Foundation 04 acceptance: private uploads, evidence and storage access.

Offline and deterministic — no live Supabase, Snowflake or OpenAI. Real PNG/JPEG/WebP
bytes are built in-memory with Pillow and a FAKE in-memory backend stands in for Storage.
Live Supabase Storage behaviour is BLOCKED in this environment and is marked SKIP rather
than faked (one placeholder below), per the prompt rules.

Covered: magic-byte validation, media-type mismatch, decoded-pixel-bomb rejection, size
cap, EXIF strip + orientation, sha256, unique PENDING key, 60-second upload/download
expiry, typed-resource resolution, foreign/unknown resource -> NOT_FOUND, path-traversal
refusal, and log/error redaction (no secret, signed URL or object path ever logged).
"""
from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from PIL import Image

from partsiq.core.contracts import ActorContext, DownloadRequest, ImageInfo, UploadRequest
from partsiq.core.errors import PartsIQError
from partsiq.core.settings import Settings
from partsiq.storage import images, service
from partsiq.storage.client import (
    BUCKET_EVIDENCE,
    BUCKET_EXPORTS,
    BUCKET_NAMEPLATES,
    PRIVATE_BUCKETS,
    StorageBackend,
    SupabaseStorageBackend,
)


# --- helpers: real image bytes, built in-memory -----------------------------

def _png_bytes(width: int = 8, height: int = 8, color: str = "red") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes(width: int = 8, height: int = 8) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), "blue").save(buf, format="JPEG")
    return buf.getvalue()


def _webp_bytes(width: int = 8, height: int = 8) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), "green").save(buf, format="WEBP")
    return buf.getvalue()


def _jpeg_with_exif_orientation(orientation: int = 6) -> bytes:
    """A landscape JPEG whose EXIF says 'rotate' — sanitize must bake and drop it."""
    img = Image.new("RGB", (12, 6), "purple")
    exif = img.getexif()
    exif[0x0112] = orientation  # 274 == Orientation
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


# --- fake backend -----------------------------------------------------------

class FakeStorageBackend:
    """Deterministic in-memory Storage; records calls, signs opaque local URLs."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.upload_calls: list[tuple[str, str, int]] = []
        self.download_calls: list[tuple[str, str, int]] = []
        self.removed: list[tuple[str, str]] = []

    async def create_signed_upload_url(self, bucket: str, object_key: str, ttl_seconds: int) -> str:
        self.upload_calls.append((bucket, object_key, ttl_seconds))
        return f"https://fake.local/upload/{bucket}/{object_key}?token=SECRET-{ttl_seconds}"

    async def create_signed_download_url(self, bucket: str, object_key: str, ttl_seconds: int) -> str:
        self.download_calls.append((bucket, object_key, ttl_seconds))
        return f"https://fake.local/download/{bucket}/{object_key}?token=SECRET-{ttl_seconds}"

    async def download(self, bucket: str, object_key: str) -> bytes:
        return self.objects[(bucket, object_key)]

    async def remove(self, bucket: str, object_key: str) -> None:
        self.removed.append((bucket, object_key))


def test_fake_backend_satisfies_protocol() -> None:
    assert isinstance(FakeStorageBackend(), StorageBackend)


# --- image validation -------------------------------------------------------

def test_validate_image_accepts_each_allowed_type_and_returns_imageinfo() -> None:
    for media_type, data in (
        ("image/png", _png_bytes()),
        ("image/jpeg", _jpeg_bytes()),
        ("image/webp", _webp_bytes()),
    ):
        info = images.validate_image(data, media_type)
        assert isinstance(info, ImageInfo)
        assert info.media_type == media_type
        assert info.width == 8 and info.height == 8
        assert len(info.sha256) == 64


def test_validate_image_sha256_is_stable() -> None:
    data = _png_bytes()
    assert images.validate_image(data, "image/png").sha256 == images.validate_image(data, "image/png").sha256


def test_magic_bytes_must_match_declared_media_type() -> None:
    png = _png_bytes()
    with pytest.raises(PartsIQError) as exc:
        images.validate_image(png, "image/jpeg")  # real PNG, declared JPEG
    assert exc.value.code == "UNSUPPORTED_MEDIA_TYPE"


def test_unsupported_media_type_is_rejected() -> None:
    with pytest.raises(PartsIQError) as exc:
        images.validate_image(_png_bytes(), "image/gif")
    assert exc.value.code == "UNSUPPORTED_MEDIA_TYPE"


def test_corrupt_bytes_are_rejected_as_validation_failed() -> None:
    # Correct PNG magic prefix but garbage body -> passes sniff, fails decode.
    corrupt = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    with pytest.raises(PartsIQError) as exc:
        images.validate_image(corrupt, "image/png")
    assert exc.value.code == "VALIDATION_FAILED"


def test_pixel_bomb_is_rejected_by_decoded_pixel_cap() -> None:
    tiny_cap = Settings(app_env="test", max_image_pixels=16)  # 4x4
    data = _png_bytes(width=100, height=100)  # 10_000 decoded pixels
    with pytest.raises(PartsIQError) as exc:
        images.validate_image(data, "image/png", settings=tiny_cap)
    assert exc.value.code == "PAYLOAD_TOO_LARGE"


def test_oversize_bytes_are_rejected_by_size_cap() -> None:
    small_cap = Settings(app_env="test", max_upload_bytes=10)
    with pytest.raises(PartsIQError) as exc:
        images.validate_image(_png_bytes(), "image/png", settings=small_cap)
    assert exc.value.code == "PAYLOAD_TOO_LARGE"


def test_sanitize_strips_exif_and_normalizes_orientation() -> None:
    original = _jpeg_with_exif_orientation(orientation=6)  # 90-degree rotate flag
    cleaned = images.sanitize(original)
    with Image.open(io.BytesIO(cleaned)) as img:
        # Orientation 6 swaps the axes; a 12x6 landscape becomes 6x12 portrait.
        assert img.size == (6, 12)
        assert not img.getexif().get(0x0112)  # Orientation tag gone
        assert "exif" not in img.info  # no EXIF block at all


# --- upload flow ------------------------------------------------------------

def _actor() -> ActorContext:
    return ActorContext(user_id=uuid4(), request_id=uuid4(), roles=[])


@pytest.mark.asyncio
async def test_create_upload_writes_unique_pending_key_and_60s_expiry() -> None:
    backend = FakeStorageBackend()
    actor = _actor()
    enquiry_id = uuid4()
    command = UploadRequest(
        enquiry_id=enquiry_id,
        expected_revision=3,
        media_type="image/jpeg",
        size_bytes=1024,
    )
    before = datetime.now(tz=timezone.utc)
    ticket = await service.create_upload(actor, command, backend=backend)

    # Exactly one signed upload to the private nameplates bucket.
    assert len(backend.upload_calls) == 1
    bucket, object_key, ttl = backend.upload_calls[0]
    assert bucket == BUCKET_NAMEPLATES
    assert ttl == service.SIGNED_URL_TTL_SECONDS == 60

    # Server-chosen PENDING key, scoped to enquiry + revision, never a caller path.
    assert object_key == f"{enquiry_id}/r3/{ticket.attachment_id}.jpg"
    assert str(ticket.attachment_id) in object_key

    # ~60s expiry window.
    delta = (ticket.expires_at - before).total_seconds()
    assert 55 <= delta <= 65


@pytest.mark.asyncio
async def test_create_upload_key_is_unique_per_call() -> None:
    backend = FakeStorageBackend()
    actor = _actor()
    command = UploadRequest(
        enquiry_id=uuid4(), expected_revision=1, media_type="image/png", size_bytes=10
    )
    t1 = await service.create_upload(actor, command, backend=backend)
    t2 = await service.create_upload(actor, command, backend=backend)
    assert t1.attachment_id != t2.attachment_id
    assert backend.upload_calls[0][1] != backend.upload_calls[1][1]


def test_upload_request_contract_rejects_oversize_and_bad_media_type() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):  # > 10 MiB
        UploadRequest(
            enquiry_id=uuid4(), expected_revision=1, media_type="image/png", size_bytes=10485761
        )
    with pytest.raises(ValidationError):  # not in allowlist
        UploadRequest(
            enquiry_id=uuid4(), expected_revision=1, media_type="image/gif", size_bytes=10
        )


# --- download flow ----------------------------------------------------------

def _download(resource_type: str, resource_id=None) -> DownloadRequest:
    return DownloadRequest(
        actor=_actor(),
        resource_type=resource_type,  # type: ignore[arg-type]
        resource_id=resource_id or uuid4(),
    )


@pytest.mark.asyncio
async def test_sign_download_resolves_typed_resource_to_bucket_and_signs_60s() -> None:
    backend = FakeStorageBackend()
    cases = {
        "attachment": BUCKET_NAMEPLATES,
        "evidence": BUCKET_EVIDENCE,
        "export": BUCKET_EXPORTS,
    }
    for resource_type, expected_bucket in cases.items():
        resource_id = uuid4()
        resolved_key = f"owner/{resource_id}.bin"

        async def resolve(actor, rtype, rid, _key=resolved_key):
            return _key

        request = _download(resource_type, resource_id)
        before = datetime.now(tz=timezone.utc)
        ticket = await service.sign_download(request, backend=backend, resolve_key=resolve)

        bucket, key, ttl = backend.download_calls[-1]
        assert bucket == expected_bucket
        assert key == resolved_key
        assert ttl == 60
        delta = (ticket.expires_at - before).total_seconds()
        assert 55 <= delta <= 65


@pytest.mark.asyncio
async def test_sign_download_foreign_or_unknown_resource_is_not_found() -> None:
    backend = FakeStorageBackend()

    async def resolve_missing(actor, rtype, rid):
        return None  # resolver denies: unknown OR foreign to this actor

    request = _download("evidence")
    with pytest.raises(PartsIQError) as exc:
        await service.sign_download(request, backend=backend, resolve_key=resolve_missing)
    assert exc.value.code == "NOT_FOUND"
    # Refused BEFORE any backend signing call.
    assert backend.download_calls == []


@pytest.mark.asyncio
async def test_sign_download_rejects_path_traversal_before_signing() -> None:
    backend = FakeStorageBackend()

    async def resolve_traversal(actor, rtype, rid):
        return "../../etc/passwd"

    request = _download("export")
    with pytest.raises(PartsIQError) as exc:
        await service.sign_download(request, backend=backend, resolve_key=resolve_traversal)
    assert exc.value.code == "NOT_FOUND"
    assert backend.download_calls == []


# --- buckets / config -------------------------------------------------------

def test_the_four_buckets_are_private_and_named() -> None:
    assert PRIVATE_BUCKETS == {"nameplates", "catalogue-evidence", "imports", "exports"}
    assert set(service.BUCKET_FOR_RESOURCE.values()) <= PRIVATE_BUCKETS


# --- redaction --------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_secret_signed_url_or_object_path_is_logged(caplog) -> None:
    backend = FakeStorageBackend()
    actor = _actor()
    enquiry_id = uuid4()

    with caplog.at_level(logging.DEBUG, logger="partsiq.storage"):
        up = await service.create_upload(
            actor,
            UploadRequest(
                enquiry_id=enquiry_id,
                expected_revision=1,
                media_type="image/png",
                size_bytes=10,
            ),
            backend=backend,
        )

        async def resolve(actor, rtype, rid):
            return f"owner/{rid}.bin"

        dl = await service.sign_download(
            _download("attachment"), backend=backend, resolve_key=resolve
        )

    logged = "\n".join(r.getMessage() for r in caplog.records)
    logged += "\n" + "\n".join(str(getattr(r, "args", "")) for r in caplog.records)
    # The emitted signed URLs, the SECRET token and the object paths must be absent.
    assert "SECRET" not in logged
    assert up.upload_url not in logged
    assert dl.url not in logged
    assert str(up.attachment_id) not in logged
    assert str(enquiry_id) not in logged


def test_error_detail_never_leaks_internal_detail() -> None:
    err = PartsIQError("NOT_FOUND", internal_detail="/nameplates/secret/path.jpg")
    assert "secret" not in err.detail
    assert err.detail == "Resource unavailable"


def test_client_import_requires_no_network_or_key() -> None:
    # Constructing the live backend must not touch the network or require a key;
    # only an actual operation would, and that is BLOCKED here.
    backend = SupabaseStorageBackend(settings=Settings(app_env="test"))
    assert backend is not None


@pytest.mark.asyncio
async def test_live_backend_without_credentials_is_dependency_unavailable() -> None:
    backend = SupabaseStorageBackend(settings=Settings(app_env="test"))
    with pytest.raises(PartsIQError) as exc:
        await backend.create_signed_download_url("exports", "k", 60)
    assert exc.value.code == "DEPENDENCY_UNAVAILABLE"
    # The safe detail must not echo any credential value.
    assert "key" not in exc.value.detail.lower() or exc.value.detail == "Storage is not configured"


@pytest.mark.skip(reason="BLOCKED: live Supabase Storage is disabled in this environment; never faked")
def test_live_supabase_roundtrip_blocked() -> None:  # pragma: no cover
    """Placeholder for the hosted upload->sign->download roundtrip, run only with a receipt."""
