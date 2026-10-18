"""F16 Photo quality feedback facade (helper ``storage.read_quality``).

Returns the stored quality verdict for an uploaded nameplate attachment: a status
(``pending``/``valid``/``rejected``), the observed dimensions and a list of actionable, named
quality WARNINGS the web maps to localised retake guidance. Confidence is NEVER accuracy
(ADR-013): this reports only concrete observable facts (width/height) and named issues
(``low_resolution``, ``too_dark``, ``possible_blur``, ...), never a fabricated accuracy percentage.

Two layers, mirroring the worker's design (``services/worker/app/features``):

* :func:`assess_photo` — a pure, local PRE-CHECK over image bytes, run BEFORE the paid vision call
  so credit is never spent on an image we can already see is unusable (an unsupported/undecodable
  image is turned back; a merely dark/low-res/slightly-blurry but decodable image stays readable
  with advisory guidance). Ported here so the single ``partsiq`` app can run the same gate without
  importing the separate worker package. Pure and fully unit-testable offline.
* :func:`read_quality` — the GET endpoint reads the STORED verdict (persisted by the worker after
  it ran the pre-check), via the injected :class:`QualityStore` port. That store is DB-backed and
  NOT configured in this fixture/offline environment, so a clean 503 is surfaced rather than a
  fabricated verdict — the live PostgreSQL adapter is wired by the owner and BLOCKED here. Owner
  access; a foreign attachment is NOT_FOUND.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable
from uuid import UUID

from partsiq.core.api_models import QualityView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.core.errors import PartsIQError

# Allowlist + thresholds mirror the nameplate OCR job and the worker pre-check so the same image is
# judged identically on both sides (an image the gate passes is the one the worker reads).
ALLOWED_MEDIA: frozenset[str] = frozenset({"image/jpeg", "image/png", "image/webp"})
_PIL_FORMAT: dict[str, str] = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}

MAX_DECODED_PIXELS = 40_000_000  # decompression-bomb guard (shared with the OCR job)
RECOMMENDED_MIN_EDGE = 600  # shortest edge below which OCR guidance is offered
DARK_MEAN_MAX = 50.0  # mean luminance (0-255) below which the photo reads as dark
BLUR_EDGE_VAR_MIN = 15.0  # edge-energy variance below which blur is *advised* (not blocking)


@dataclass(frozen=True)
class PhotoProbe:
    """A candidate nameplate photo to pre-check, as raw bytes plus the claimed media type."""

    image_bytes: bytes
    media_type: str


@dataclass(frozen=True)
class PhotoVerdict:
    """The local pre-check verdict: whether the image is usable, plus observed facts and issues."""

    readable: bool
    issues: list[str] = field(default_factory=list)
    width: int = 0
    height: int = 0


def assess_photo(probe: PhotoProbe) -> PhotoVerdict:
    """Assess a candidate nameplate photo without any paid call; raise nothing, return a verdict.

    Ported from ``services/worker/app/features/f16_photo_quality_feedback.py``: an
    unsupported/undecodable/oversize image is turned back (``readable=False``); a decodable,
    supported image stays readable, with low-resolution/darkness/blur reported as ADVISORY issues.
    """
    from PIL import Image, ImageFilter, ImageStat, UnidentifiedImageError

    if probe.media_type not in ALLOWED_MEDIA:
        return PhotoVerdict(readable=False, issues=["unsupported_format"])

    try:
        with Image.open(io.BytesIO(probe.image_bytes)) as verify_img:
            verify_img.verify()  # detect truncated/corrupt data before any pixel decode
        with Image.open(io.BytesIO(probe.image_bytes)) as img:
            width, height = img.size  # lazy — no pixels decoded yet
            fmt = img.format
            if width * height > MAX_DECODED_PIXELS:
                return PhotoVerdict(
                    readable=False, issues=["image_too_large"], width=width, height=height
                )
            if fmt not in _PIL_FORMAT or _PIL_FORMAT[fmt] != probe.media_type:
                return PhotoVerdict(
                    readable=False, issues=["format_mismatch"], width=width, height=height
                )
            gray = img.convert("L")  # decodes pixels (now bounded by the bomb guard above)
            mean_luma = ImageStat.Stat(gray).mean[0]
            edges = gray.filter(ImageFilter.FIND_EDGES)
            # Crop the 2px frame: FIND_EDGES treats the border as a hard edge, which would make a
            # featureless (blurry) photo look sharp. Measure interior energy only.
            margin = 2
            if edges.width > 2 * margin and edges.height > 2 * margin:
                edges = edges.crop(
                    (margin, margin, edges.width - margin, edges.height - margin)
                )
            edge_variance = ImageStat.Stat(edges).var[0]
    except (UnidentifiedImageError, OSError, ValueError):
        return PhotoVerdict(readable=False, issues=["undecodable_image"])

    issues: list[str] = []
    if min(width, height) < RECOMMENDED_MIN_EDGE:
        issues.append("low_resolution")
    if mean_luma < DARK_MEAN_MAX:
        issues.append("too_dark")
    if edge_variance < BLUR_EDGE_VAR_MIN:
        issues.append("possible_blur")  # advisory: a blurry but decodable image is still allowed
    return PhotoVerdict(readable=True, issues=issues, width=width, height=height)


@runtime_checkable
class QualityStore(Protocol):
    """Read port over the stored per-attachment quality verdict (RLS/ownership-scoped in prod).

    ``read`` authorises the actor against the attachment's enquiry (foreign → NOT_FOUND) and
    returns the persisted :class:`QualityView` the worker produced from :func:`assess_photo`.
    """

    async def read(self, actor: ActorContext, attachment_id: UUID) -> QualityView: ...


def _require_quality_store(container: AppContainer) -> QualityStore:
    store = getattr(container, "attachment_quality", None)
    if store is None or not hasattr(store, "read"):
        raise PartsIQError(
            "DEPENDENCY_UNAVAILABLE",
            internal_detail="attachment-quality store is not configured in this environment",
        )
    return store


async def read_quality(
    actor: ActorContext,
    attachment_id: UUID,
    *,
    container: AppContainer,
    store: QualityStore | None = None,
) -> QualityView:
    """Read the stored quality verdict for one uploaded attachment (owner access; 404 foreign)."""
    store = store or _require_quality_store(container)
    return await store.read(actor, attachment_id)
