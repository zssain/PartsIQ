"""Shared catalogue source model: typed records, the repository interface and canonical hashing.

Foundation 02. Both :mod:`partsiq.catalogue.snowflake_repository` and
:mod:`partsiq.catalogue.fixture_repository` implement the SAME
:class:`CatalogueSource` protocol and return the SAME typed
:class:`~partsiq.core.api_models.CatalogueSnapshot` /
:class:`~partsiq.core.api_models.CatalogueRecord` shape. The source is selected explicitly
by ``Settings.data_source`` (``fixture`` or ``snowflake``) — there is NO automatic fallback
between them (ARCHITECTURE section 5, DATA_OWNERSHIP). A Snowflake failure never silently
switches the data source.

This module is pure: it performs no I/O and lazy-imports nothing external. It defines the
canonical content digest (``content_sha256``) that both repositories and the activation
pipeline compute identically so a round-trip can be verified byte-for-byte.
"""
from __future__ import annotations

import hashlib
import json
from typing import Literal, Protocol, runtime_checkable
from uuid import UUID

from partsiq.core.api_models import CatalogueRecord, CatalogueSnapshot

CatalogueSourceName = Literal["snowflake", "fixture"]

# The nine catalogue entity types that may appear in a snapshot payload. These mirror the
# legacy PostgreSQL entities (DATA_OWNERSHIP "Snapshot payload contracts"). Stock lives in a
# dedicated Snowflake table and is not carried as a catalogue RECORD here.
CATALOGUE_ENTITY_TYPES: frozenset[str] = frozenset(
    {
        "equipment_families",
        "equipment_models",
        "model_configurations",
        "parts",
        "part_aliases",
        "part_compatibility",
        "part_supersessions",
        "warehouses",
        "warehouse_transfer_routes",
    }
)


def canonical_record_json(record: CatalogueRecord) -> str:
    """Stable JSON for one record: entity type, key and sorted payload, numeric ids preserved."""
    return json.dumps(
        {
            "entity_type": record.entity_type,
            "entity_key": record.entity_key,
            "payload": record.payload,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def row_sha256(record: CatalogueRecord) -> str:
    """Per-row digest used to compare a single remote row against its manifest value."""
    return hashlib.sha256(canonical_record_json(record).encode("utf-8")).hexdigest()


def content_sha256(records: list[CatalogueRecord]) -> str:
    """Order-independent SHA-256 over a snapshot's records.

    Records are sorted by (entity_type, entity_key) before hashing so the digest depends only
    on content, never on row order. Numeric catalogue ids inside payloads are preserved (never
    renumbered or coerced to UUIDs).
    """
    ordered = sorted(records, key=lambda r: (r.entity_type, r.entity_key))
    canonical = "[" + ",".join(canonical_record_json(r) for r in ordered) + "]"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_snapshot(
    *,
    version_id: UUID,
    source: CatalogueSourceName,
    records: list[CatalogueRecord],
) -> CatalogueSnapshot:
    """Assemble a :class:`CatalogueSnapshot` with a freshly computed canonical digest."""
    return CatalogueSnapshot(
        version_id=version_id,
        source=source,
        content_sha256=content_sha256(records),
        records=records,
    )


@runtime_checkable
class CatalogueSource(Protocol):
    """Common read interface implemented by both the Snowflake and fixture repositories.

    The caller selects the implementation explicitly from ``Settings.data_source``; there is
    no fallback. ``source`` labels every snapshot so the UI can display which source served it.
    """

    source: CatalogueSourceName

    def read_version(self, version_id: UUID) -> CatalogueSnapshot:
        """Return the immutable snapshot for a requested VERSION_ID with a verified digest."""
        ...
