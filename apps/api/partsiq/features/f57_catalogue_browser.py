"""F57 Catalogue browser facade (helpers ``catalogue.browse`` / ``catalogue.get_part``).

Read-only browse + single-part detail over the VALIDATED ACTIVE published catalogue version
(``container.catalogue``). ``browse`` applies optional free-text / model / category filters and
keyset-paginates by ascending part id; ``get_part`` returns one published part by number (404 if
unknown). It only ever returns rows of the active published version — unpublished import-staging
rows live elsewhere and are never read here (ported from the legacy gateway F57 behaviour).

Determinism/safety: the free-text ``query`` is a literal case-insensitive substring match over the
part number and bilingual names, so a query string can never become SQL (there is no SQL here; the
live read adapter binds it as a parameter). ``model_id`` is resolved to the active model's
compatible part set via the catalogue compatibility edges, so browsing by machine shows only parts
that actually fit it. Access is ``customer``; the browse reveals catalogue facts only, no inventory.

Serves real seed-42 data in fixture mode by deriving the typed records from the active snapshot; in
DB mode the live read store is not configured, so a clean 503 is surfaced.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from uuid import UUID

from partsiq.core.api_models import (
    CataloguePage,
    CataloguePart,
    CatalogueQuery,
    CatalogueSnapshot,
)
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.core.errors import PartsIQError
from partsiq.search.repository import CatalogueSnapshotRepository
from partsiq_common.text import part_number_key


@dataclass(frozen=True, slots=True)
class _Part:
    """The browse-relevant projection of one active catalogue part record."""

    id: int
    part_number: str
    name_en: str
    name_ar: str
    category: str
    unit_of_measure: str
    is_active: bool


def _active(container: AppContainer) -> tuple[CatalogueSnapshot, UUID]:
    """Return the validated active snapshot + its version id, or raise 503 when none is wired."""
    if container.catalogue is None:
        raise PartsIQError(
            "DEPENDENCY_UNAVAILABLE",
            internal_detail="catalogue read store not configured in this environment",
        )
    version_ids = container.catalogue.available_version_ids()
    if not version_ids:
        raise PartsIQError(
            "DEPENDENCY_UNAVAILABLE", internal_detail="no active catalogue version available"
        )
    version_id = version_ids[0]
    snapshot = container.catalogue.read_version(version_id)
    # Re-validate the active snapshot (STALE_CATALOGUE if invalid) and reject an unknown version
    # key the same way the search repository does; the repository is the single validation gate.
    CatalogueSnapshotRepository.from_active_snapshot(snapshot)
    return snapshot, version_id


def _parts(snapshot: CatalogueSnapshot) -> list[_Part]:
    """Every part row of the active snapshot, ordered by ascending catalogue id (stable paging)."""
    parts: list[_Part] = []
    for record in snapshot.records:
        if record.entity_type != "parts":
            continue
        payload = record.payload
        part_id = int(payload["id"]) if "id" in payload else int(record.entity_key)
        parts.append(
            _Part(
                id=part_id,
                part_number=str(payload["part_number"]),
                name_en=str(payload["name_en"]),
                name_ar=str(payload["name_ar"]),
                category=str(payload["category"]),
                unit_of_measure=str(payload["unit_of_measure"]),
                is_active=bool(payload["is_active"]),
            )
        )
    parts.sort(key=lambda p: p.id)
    return parts


async def _model_part_ids(
    container: AppContainer, snapshot: CatalogueSnapshot, model_id: int
) -> set[int] | None:
    """Part ids compatible with any configuration of ``model_id``; None if the model is unknown."""
    repo = CatalogueSnapshotRepository.from_active_snapshot(snapshot)
    model = next((m for m in await repo.fetch_models() if m.id == model_id), None)
    if model is None:
        return None
    part_ids: set[int] = set()
    for config in model.configurations:
        for row in await repo.fetch_compatibility(config.id):
            part_ids.add(row.part_id)
    return part_ids


def _encode_cursor(part_id: int) -> str:
    return base64.urlsafe_b64encode(str(part_id).encode("ascii")).decode("ascii")


def _decode_cursor(value: str) -> int:
    try:
        return int(base64.urlsafe_b64decode(value.encode("ascii")).decode("ascii"))
    except (ValueError, TypeError) as exc:
        raise PartsIQError(
            "VALIDATION_FAILED", internal_detail="cursor is not a valid pagination token"
        ) from exc


def _matches(
    part: _Part, query: str | None, category: str | None, allowed: set[int] | None
) -> bool:
    if allowed is not None and part.id not in allowed:
        return False
    if category is not None and part.category != category:
        return False
    if query:
        needle = query.strip().casefold()
        haystack = f"{part.part_number} {part.name_en} {part.name_ar}".casefold()
        if needle and needle not in haystack:
            return False
    return True


def _to_part(part: _Part, version_id: UUID) -> CataloguePart:
    return CataloguePart(
        id=part.id,
        part_number=part.part_number,
        name_en=part.name_en,
        name_ar=part.name_ar,
        category=part.category,
        unit_of_measure=part.unit_of_measure,
        is_active=part.is_active,
        catalogue_version_id=version_id,
    )


async def browse(
    actor: ActorContext, query: CatalogueQuery, *, container: AppContainer
) -> CataloguePage:
    """Browse the active published catalogue with filters + keyset paging by ascending part id."""
    _ = actor  # a verified actor is always present; customer access needs no role
    snapshot, version_id = _active(container)
    allowed: set[int] | None = None
    if query.model_id is not None:
        allowed = await _model_part_ids(container, snapshot, query.model_id)
        if not allowed:
            # Unknown model, or a model with no compatible parts, is simply an empty page.
            return CataloguePage(items=[], next_cursor=None)
    after_id = _decode_cursor(query.cursor) if query.cursor else None
    ordered = [
        part
        for part in _parts(snapshot)
        if (after_id is None or part.id > after_id)
        and _matches(part, query.query, query.category, allowed)
    ]
    window = ordered[: query.limit + 1]
    has_more = len(window) > query.limit
    page = window[: query.limit]
    next_cursor = _encode_cursor(page[-1].id) if has_more and page else None
    return CataloguePage(
        items=[_to_part(part, version_id) for part in page], next_cursor=next_cursor
    )


async def get_part(
    actor: ActorContext, part_number: str, *, container: AppContainer
) -> CataloguePart:
    """Return one published part by number; an unknown/unpublished number is a 404."""
    _ = actor  # customer access needs no role
    snapshot, version_id = _active(container)
    key = part_number_key(part_number)
    match = next((p for p in _parts(snapshot) if part_number_key(p.part_number) == key), None)
    if match is None:
        raise PartsIQError(
            "NOT_FOUND",
            detail="The requested part number is not in the active catalogue.",
            internal_detail=f"part number {part_number} not found",
        )
    return _to_part(match, version_id)
