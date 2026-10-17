"""Image validation and sanitization for private uploads (ported from worker nameplate job).

Defence in depth before any image reaches the vision model (SECURITY.md, prompt 04 step 5-6):

* magic-byte sniff — the real leading bytes must match the DECLARED media type, so a
  spoofed extension or content type cannot smuggle a different payload;
* media-type allowlist — only ``image/jpeg``, ``image/png`` and ``image/webp``;
* size cap — raw bytes must be within ``Settings.max_upload_bytes`` (10 MiB contract bound);
* decoded-pixel cap — ``Image.verify`` plus an INDEPENDENT ``width * height`` limit from
  ``Settings.max_image_pixels`` guards the worker against a decompression bomb;
* EXIF strip + orientation normalize — ``sanitize`` bakes in orientation and re-encodes
  with no metadata before the bytes are handed to the provider.

:func:`validate_image` returns the :class:`ImageInfo` contract (width, height, media_type,
sha256). Errors are raised as :class:`PartsIQError` with a public code and a safe detail;
the raw bytes, object path and provider internals never appear in a message.
"""
from __future__ import annotations

import hashlib
import io

from PIL import Image, ImageOps, UnidentifiedImageError

from partsiq.core.contracts import ImageInfo
from partsiq.core.errors import PartsIQError
from partsiq.core.settings import Settings, load_settings

# Pillow format name -> media type. Also the media-type allowlist (prompt 04).
_ALLOWED: dict[str, str] = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
ALLOWED_MEDIA_TYPES: frozenset[str] = frozenset(_ALLOWED.values())

# ImageInfo bounds the declared width/height to 12000 each; mirror that here so a huge
# single-axis image is rejected before pydantic validation would raise an opaque error.
MAX_DIMENSION = 12000

# Longest edge of the sanitized preview handed to the vision provider.
PREVIEW_LONGEST_EDGE = 2048

# media_type -> acceptable magic-byte prefixes (content-spoofing defence).
_MAGIC: dict[str, tuple[bytes, ...]] = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/webp": (b"RIFF",),  # plus 'WEBP' at bytes 8..12, checked in sniff_media_type
}


def sniff_media_type(data: bytes, media_type: str) -> bool:
    """Confirm the real leading bytes match the DECLARED image type."""
    prefixes = _MAGIC.get(media_type)
    if prefixes is None:
        return False
    if not any(data.startswith(prefix) for prefix in prefixes):
        return False
    if media_type == "image/webp":
        return len(data) >= 12 and data[8:12] == b"WEBP"
    return True


def validate_image(
    image: bytes, media_type: str, *, settings: Settings | None = None
) -> ImageInfo:
    """Decode and bound a candidate image; raise a safe typed error on anything invalid.

    Order matters: cheap checks (allowlist, size, magic) run before the decode so an
    attacker cannot force an expensive operation with a trivially rejectable payload.
    """
    settings = settings or load_settings()

    if media_type not in ALLOWED_MEDIA_TYPES:
        raise PartsIQError(
            "UNSUPPORTED_MEDIA_TYPE", internal_detail="media type not allowed"
        )
    if len(image) > settings.max_upload_bytes:
        raise PartsIQError(
            "PAYLOAD_TOO_LARGE", internal_detail="image exceeds the upload size cap"
        )
    if not sniff_media_type(image, media_type):
        raise PartsIQError(
            "UNSUPPORTED_MEDIA_TYPE",
            internal_detail="magic bytes do not match declared media type",
        )

    sha256 = hashlib.sha256(image).hexdigest()
    try:
        with Image.open(io.BytesIO(image)) as probe:
            probe.verify()  # detect truncated/corrupt data without a full decode
        with Image.open(io.BytesIO(image)) as decoded:
            width, height = decoded.size
            fmt = decoded.format
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise PartsIQError(
            "VALIDATION_FAILED",
            internal_detail=f"undecodable image: {type(exc).__name__}",
        ) from exc

    if fmt not in _ALLOWED or _ALLOWED[fmt] != media_type:
        raise PartsIQError(
            "UNSUPPORTED_MEDIA_TYPE",
            internal_detail="decoded format does not match declared media type",
        )
    if (
        width > MAX_DIMENSION
        or height > MAX_DIMENSION
        or (width * height) > settings.max_image_pixels
    ):
        raise PartsIQError(
            "PAYLOAD_TOO_LARGE", internal_detail="image exceeds the decoded-pixel cap"
        )
    return ImageInfo(width=width, height=height, media_type=media_type, sha256=sha256)


def sanitize(image: bytes) -> bytes:
    """Normalize orientation, strip EXIF, bound the size; return a clean JPEG.

    The result carries NO metadata — EXIF (including GPS) is dropped by re-encoding —
    and orientation is baked into the pixels so downstream readers need no EXIF.
    """
    with Image.open(io.BytesIO(image)) as decoded:
        oriented = ImageOps.exif_transpose(decoded)  # bake orientation, drop EXIF
        if oriented is None:  # pragma: no cover - exif_transpose returns the image
            oriented = decoded
        oriented = oriented.convert("RGB")
        oriented.thumbnail((PREVIEW_LONGEST_EDGE, PREVIEW_LONGEST_EDGE))
        buffer = io.BytesIO()
        oriented.save(buffer, format="JPEG", quality=90)  # re-encode with no metadata
    return buffer.getvalue()


__all__ = [
    "ALLOWED_MEDIA_TYPES",
    "MAX_DIMENSION",
    "PREVIEW_LONGEST_EDGE",
    "sanitize",
    "sniff_media_type",
    "validate_image",
]
