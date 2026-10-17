"""Fixture catalogue source (``DATA_SOURCE=fixture``) — foundation 02.

Reads versioned catalogue records from a local JSON fixture and returns the SAME typed
:class:`~partsiq.core.api_models.CatalogueSnapshot` shape as the Snowflake repository, labelled
``source="fixture"`` so the UI can show which source served the data. This is the explicit
offline/demo mode; it is NEVER selected as an automatic fallback from a Snowflake failure
(ARCHITECTURE section 5, DATA_OWNERSHIP). Selection is by ``Settings.data_source`` alone.

The fixture file (authored later by prompt 05 at ``fixtures/catalogue.json``) maps a version id
to a list of records. For deterministic offline tests a repository can also be constructed
directly from an in-memory mapping via :meth:`FixtureCatalogueRepository.from_versions`.

Fixture format (``fixtures/catalogue.json``)::

    {
      "versions": {
        "<version-uuid>": [
          {"entity_type": "parts", "entity_key": "101",
           "payload": {"part_number": "FLT-101", ...}},
          ...
        ]
      }
    }

A single flat ``{"records": [...]}`` document is also accepted and treated as one version whose
id is taken from ``Settings`` / the first requested id.
"""
from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from partsiq.core.api_models import CatalogueRecord, CatalogueSnapshot
from partsiq.core.errors import PartsIQError

from .models import CatalogueSourceName, build_snapshot

_SOURCE: CatalogueSourceName = "fixture"


def _coerce_records(raw: list[dict[str, object]]) -> list[CatalogueRecord]:
    records: list[CatalogueRecord] = []
    for item in raw:
        payload = item["payload"]
        if not isinstance(payload, dict):
            raise PartsIQError(
                "DEPENDENCY_UNAVAILABLE",
                detail="Catalogue fixture is malformed.",
                internal_detail="record payload must be an object",
            )
        records.append(
            CatalogueRecord(
                entity_type=str(item["entity_type"]),
                entity_key=str(item["entity_key"]),
                payload=dict(payload),
            )
        )
    return records


class FixtureCatalogueRepository:
    """A :class:`~partsiq.catalogue.models.CatalogueSource` backed by local JSON fixtures."""

    source: CatalogueSourceName = _SOURCE

    def __init__(self, versions: dict[UUID, list[CatalogueRecord]]) -> None:
        self._versions = versions

    # --- constructors ----------------------------------------------------

    @classmethod
    def from_versions(cls, versions: dict[UUID, list[CatalogueRecord]]) -> "FixtureCatalogueRepository":
        """Build from an in-memory mapping — used by deterministic offline tests."""
        return cls(dict(versions))

    @classmethod
    def from_file(cls, path: str | Path, *, default_version_id: UUID | None = None) -> "FixtureCatalogueRepository":
        """Load the fixture document from ``path``.

        Supports the ``{"versions": {...}}`` layout and the flat ``{"records": [...]}`` layout
        (the latter requires ``default_version_id`` or an ``id``/``version_id`` field).
        """
        file_path = Path(path)
        if not file_path.is_file():
            raise PartsIQError(
                "DEPENDENCY_UNAVAILABLE",
                detail="Catalogue fixture is unavailable.",
                internal_detail=f"fixture file not found: {file_path}",
            )
        document = json.loads(file_path.read_text(encoding="utf-8"))
        versions: dict[UUID, list[CatalogueRecord]] = {}
        if isinstance(document, dict) and "versions" in document:
            for raw_id, raw_records in document["versions"].items():
                versions[UUID(str(raw_id))] = _coerce_records(list(raw_records))
        else:
            version_id = (
                default_version_id
                or (UUID(str(document["version_id"])) if "version_id" in document else None)
                or (UUID(str(document["id"])) if "id" in document else None)
            )
            if version_id is None:
                raise PartsIQError(
                    "DEPENDENCY_UNAVAILABLE",
                    detail="Catalogue fixture is malformed.",
                    internal_detail="flat fixture lacks a version id and no default was supplied",
                )
            versions[version_id] = _coerce_records(list(document["records"]))
        return cls(versions)

    # --- CatalogueSource interface --------------------------------------

    def read_version(self, version_id: UUID) -> CatalogueSnapshot:
        """Return the fixture snapshot for ``version_id`` with a freshly computed digest."""
        records = self._versions.get(version_id)
        if records is None:
            raise PartsIQError(
                "NOT_FOUND",
                detail="The requested catalogue version is unavailable.",
                internal_detail=f"fixture has no version {version_id}",
            )
        return build_snapshot(version_id=version_id, source=_SOURCE, records=records)

    def available_version_ids(self) -> list[UUID]:
        """Version ids present in the fixture (helper for tooling/tests; not the read path)."""
        return list(self._versions)
