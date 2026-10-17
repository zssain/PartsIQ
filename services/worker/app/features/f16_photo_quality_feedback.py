"""F16 Photo quality feedback (owner: worker; depends on 16, 19).

A cheap, local pre-check run BEFORE the paid vision call (ADR: never spend credit on an
image we can already see is unusable). It checks decodability, media type, dimensions and a
darkness/blur heuristic, and returns actionable retake guidance as machine codes the web maps
to localized instructions.

The heuristic is advisory: an UNSUPPORTED or UNDECODABLE image is turned back
(``readable=False``), but a decodable image that is merely low-resolution, dark or slightly
blurry stays ``readable=True`` with guidance — a readable image is allowed despite a
noncritical blur warning. No OCR confidence percentage is produced here: confidence is never
accuracy (ADR-013), so this pre-check reports only concrete, observable facts (dimensions)
and named quality issues, never a fabricated percentage.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field

from PIL import Image, ImageFilter, ImageStat, UnidentifiedImageError

# Mirrors the nameplate job's allowlist (services/worker/app/jobs/nameplate.py).
ALLOWED_MEDIA: frozenset[str] = frozenset({"image/jpeg", "image/png", "image/webp"})
_PIL_FORMAT: dict[str, str] = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}

MAX_DECODED_PIXELS = 40_000_000   # decompression-bomb guard (shared with the OCR job)
RECOMMENDED_MIN_EDGE = 600        # shortest edge below which OCR guidance is offered
DARK_MEAN_MAX = 50.0              # mean luminance (0-255) below which the photo reads as dark
BLUR_EDGE_VAR_MIN = 15.0          # edge-energy variance below which blur is *advised* (not blocking)


@dataclass(frozen=True)
class F16Request:
    image_bytes: bytes
    media_type: str


@dataclass(frozen=True)
class F16Result:
    readable: bool
    issues: list[str] = field(default_factory=list)
    width: int = 0
    height: int = 0


def assess_photo(request: F16Request) -> F16Result:
    """Assess a candidate nameplate photo without any paid call; raise nothing, return a verdict."""
    if request.media_type not in ALLOWED_MEDIA:
        # Unsupported format is rejected (the only non-advisory failure besides a broken decode).
        return F16Result(readable=False, issues=["unsupported_format"])

    try:
        with Image.open(io.BytesIO(request.image_bytes)) as probe:
            probe.verify()  # detect truncated/corrupt data before any pixel decode
        with Image.open(io.BytesIO(request.image_bytes)) as img:
            width, height = img.size  # lazy — no pixels decoded yet
            fmt = img.format
            if width * height > MAX_DECODED_PIXELS:
                return F16Result(readable=False, issues=["image_too_large"], width=width, height=height)
            if fmt not in _PIL_FORMAT or _PIL_FORMAT[fmt] != request.media_type:
                return F16Result(readable=False, issues=["format_mismatch"], width=width, height=height)
            gray = img.convert("L")  # decodes pixels (now bounded by the bomb guard above)
            mean_luma = ImageStat.Stat(gray).mean[0]
            edges = gray.filter(ImageFilter.FIND_EDGES)
            # Crop the 2px frame: FIND_EDGES treats the image border as a hard edge, which would
            # otherwise make a featureless (blurry) photo look sharp. Measure interior energy only.
            margin = 2
            if edges.width > 2 * margin and edges.height > 2 * margin:
                edges = edges.crop((margin, margin, edges.width - margin, edges.height - margin))
            edge_variance = ImageStat.Stat(edges).var[0]
    except (UnidentifiedImageError, OSError, ValueError):
        return F16Result(readable=False, issues=["undecodable_image"])

    # Decodable and a supported format -> readable. The checks below are advisory guidance only.
    issues: list[str] = []
    if min(width, height) < RECOMMENDED_MIN_EDGE:
        issues.append("low_resolution")
    if mean_luma < DARK_MEAN_MAX:
        issues.append("too_dark")
    if edge_variance < BLUR_EDGE_VAR_MIN:
        issues.append("possible_blur")  # advisory: a blurry but decodable image is still allowed
    return F16Result(readable=True, issues=issues, width=width, height=height)
