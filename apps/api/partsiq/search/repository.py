"""Retrieval port for the search domain, plus a catalogue-snapshot implementation.

Ported from the legacy ``services/search/app/repository.py`` (foundation 06). The legacy
repository held all SQL and read PostgreSQL directly. In the single-package build the active
catalogue is served by the foundation-02/05 catalogue layer, so retrieval reads a VALIDATED
ACTIVE :class:`~partsiq.core.api_models.CatalogueSnapshot` rather than an arbitrary latest
Snowflake/Postgres row (CONSTRAINTS: "Search/read operations must use the validated active
catalogue version").

Two surfaces are defined:

* :class:`SearchRepository` — the retrieval PORT (a Protocol). ``SearchService`` depends only on
  this. The live asyncpg + pgvector implementation is BLOCKED in this environment (the driver is
  not installed and no database allowance is confirmed); it would bind the same method surface to
  one connection pool.
* :class:`CatalogueSnapshotRepository` — a pure, offline implementation that derives the typed
  records (:class:`ModelRecord`, :class:`PartRecord`, :class:`CompatibilityRow`, …) from one
  snapshot. Stock is NOT carried as a catalogue RECORD (it lives in a dedicated stock table), so
  stock and semantic similarities are supplied by injected sources. Tests seed both from the
  seed-42 fixture catalogue; a fake encoder provides fixed unit vectors without loading BGE-M3.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from partsiq.catalogue.validation import validate_snapshot
from partsiq.core.api_models import CatalogueRecord, CatalogueSnapshot
from partsiq.core.errors import PartsIQError
from partsiq_common.text import part_number_key

from .fulfilment import WarehouseStock
from .identification import ConfigurationRecord, ModelRecord

MAX_SUPERSESSION_DEPTH = 20


@dataclass(frozen=True, slots=True)
class PartRecord:
    id: int
    part_number: str
    name_en: str
    name_ar: str
    description_en: str
    category: str
    unit_of_measure: str
    is_active: bool
    aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CompatibilityRow:
    part_id: int
    quantity_per_unit: float
    source_reference: str


@dataclass(frozen=True, slots=True)
class CompatibleMachine:
    configuration_id: int
    brand: str
    model_code: str
    display_name: str
    config_code: str
    quantity_per_unit: float


@dataclass(frozen=True, slots=True)
class StockObservation:
    """A netted stock reading for one (part, warehouse): already on-hand minus reserved."""

    warehouse_code: str
    warehouse_name: str
    region: str
    available: int
    observed_at: datetime


@runtime_checkable
class SearchRepository(Protocol):
    """The retrieval port the search use cases depend on. One active catalogue version only."""

    async def fetch_models(self) -> list[ModelRecord]: ...

    async def fetch_model_for_configuration(self, configuration_id: int) -> ModelRecord | None: ...

    async def fetch_compatibility(self, configuration_id: int) -> list[CompatibilityRow]: ...

    async def fetch_supersession_chains(self, part_ids: Sequence[int]) -> dict[int, list[int]]: ...

    async def fetch_parts(self, part_ids: Sequence[int]) -> dict[int, PartRecord]: ...

    async def find_part_ids_by_number_keys(self, keys: Sequence[str]) -> dict[str, int]: ...

    async def fetch_stock(self, part_ids: Sequence[int]) -> dict[int, list[WarehouseStock]]: ...

    async def fetch_transfer_days(self) -> dict[tuple[str, str], int]: ...

    async def fetch_warehouses(self) -> list[dict[str, str]]: ...

    async def fetch_compatible_machines(self, part_id: int, limit: int = 50) -> list[CompatibleMachine]: ...

    async def fetch_semantic_similarities(
        self, query_vector: str, model_name: str, part_ids: Sequence[int]
    ) -> dict[int, float]: ...


class StockSource(Protocol):
    """Netted stock readings keyed by part id. Separate from the catalogue (stock is not a record)."""

    def observations(self, part_id: int) -> list[StockObservation]: ...


class MappingStockSource:
    """A deterministic in-memory :class:`StockSource` seeded from a mapping.

    ``readings`` maps a part id to its per-warehouse netted observations. A warehouse with no
    reading reports zero (never a silent gap), matching the legacy "warehouses without a row
    report zero" behaviour. Negative nets are preserved here and clamped by the planner (F32).
    """

    def __init__(self, readings: dict[int, list[StockObservation]]) -> None:
        self._readings = readings

    def observations(self, part_id: int) -> list[StockObservation]:
        return list(self._readings.get(part_id, []))


def _as_int(value: object) -> int:
    """Coerce a validated-snapshot payload value (typed ``object``) to ``int``."""
    if isinstance(value, bool):  # a bool is an int subclass but never a catalogue id
        raise TypeError("expected an integer, received a boolean")
    if isinstance(value, int):
        return value
    return int(str(value))


def _as_float(value: object) -> float:
    """Coerce a validated-snapshot payload value (typed ``object``) to ``float``."""
    if isinstance(value, bool):
        raise TypeError("expected a number, received a boolean")
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value))


class CatalogueSnapshotRepository:
    """A :class:`SearchRepository` backed by one VALIDATED ACTIVE catalogue snapshot.

    All typed records are derived once from the snapshot's records; the numeric catalogue ids
    carried on ``parts`` / ``model_configurations`` payloads are preserved exactly (never
    renumbered). Stock and semantic similarities come from injected sources because stock is not
    a catalogue record and pgvector retrieval is a BLOCKED live dependency here.
    """

    def __init__(
        self,
        snapshot: CatalogueSnapshot,
        *,
        stock: StockSource | None = None,
        semantic: dict[int, float] | None = None,
    ) -> None:
        self._snapshot = snapshot
        self._stock = stock or MappingStockSource({})
        self._semantic = dict(semantic or {})
        self._build()

    # --- constructors ----------------------------------------------------

    @classmethod
    def from_active_snapshot(
        cls,
        snapshot: CatalogueSnapshot,
        *,
        stock: StockSource | None = None,
        semantic: dict[int, float] | None = None,
    ) -> "CatalogueSnapshotRepository":
        """Build from the VALIDATED ACTIVE catalogue version, never an arbitrary latest row.

        The snapshot is re-validated with the foundation-02 pipeline here; a snapshot with any
        validation issue raises ``STALE_CATALOGUE`` rather than serving a version that was never
        validated (CONSTRAINTS: search reads use the validated active catalogue version).
        """
        issues = validate_snapshot(snapshot)
        if issues:
            raise PartsIQError(
                "STALE_CATALOGUE",
                detail="The active catalogue version is not valid for search.",
                internal_detail=f"{len(issues)} validation issue(s) in version {snapshot.version_id}",
            )
        return cls(snapshot, stock=stock, semantic=semantic)

    # --- derivation ------------------------------------------------------

    def _grouped(self) -> dict[str, list[CatalogueRecord]]:
        grouped: dict[str, list[CatalogueRecord]] = defaultdict(list)
        for record in self._snapshot.records:
            grouped[record.entity_type].append(record)
        return grouped

    def _build(self) -> None:
        grouped = self._grouped()

        families = {
            str(r.payload["code"]): (str(r.payload["name_en"]), str(r.payload["name_ar"]))
            for r in grouped.get("equipment_families", [])
        }

        # Configurations grouped by their owning model (brand, model_code).
        configs_by_model: dict[tuple[str, str], list[ConfigurationRecord]] = defaultdict(list)
        self._config_to_model: dict[int, tuple[str, str]] = {}
        for record in grouped.get("model_configurations", []):
            payload = record.payload
            config_id = _as_int(payload["id"]) if "id" in payload else int(record.entity_key)
            model_key = (str(payload["brand"]), str(payload["model_code"]))
            configs_by_model[model_key].append(
                ConfigurationRecord(
                    id=config_id,
                    config_code=str(payload["config_code"]),
                    description=str(payload.get("description", "")),
                    serial_start=_as_int(payload["serial_start"]),
                    serial_end=_as_int(payload["serial_end"]),
                )
            )
            self._config_to_model[config_id] = model_key

        self._models: list[ModelRecord] = []
        self._model_id_by_key: dict[tuple[str, str], int] = {}
        for index, record in enumerate(
            sorted(grouped.get("equipment_models", []), key=lambda r: r.entity_key), start=1
        ):
            payload = record.payload
            model_key = (str(payload["brand"]), str(payload["model_code"]))
            family_code = str(payload["family_code"])
            family_en, family_ar = families.get(family_code, ("", ""))
            self._model_id_by_key[model_key] = index
            self._models.append(
                ModelRecord(
                    id=index,
                    brand=model_key[0],
                    model_code=model_key[1],
                    display_name=str(payload["display_name"]),
                    rated_output=(str(payload["rated_output"]) if payload.get("rated_output") else None),
                    family_code=family_code,
                    family_name_en=family_en,
                    family_name_ar=family_ar,
                    configurations=tuple(
                        sorted(configs_by_model.get(model_key, ()), key=lambda c: c.serial_start)
                    ),
                )
            )
        self._model_by_config: dict[int, ModelRecord] = {}
        by_key = {(m.brand, m.model_code): m for m in self._models}
        for config_id, model_key in self._config_to_model.items():
            if model_key in by_key:
                self._model_by_config[config_id] = by_key[model_key]

        # Aliases grouped by part number.
        aliases_by_number: dict[str, list[str]] = defaultdict(list)
        for record in grouped.get("part_aliases", []):
            aliases_by_number[str(record.payload["part_number"])].append(str(record.payload["alias"]))

        # Parts keyed by numeric id and by part-number key.
        self._parts: dict[int, PartRecord] = {}
        self._part_id_by_number: dict[str, int] = {}
        self._id_by_number_key: dict[str, int] = {}
        for record in grouped.get("parts", []):
            payload = record.payload
            part_id = _as_int(payload["id"]) if "id" in payload else int(record.entity_key)
            number = str(payload["part_number"])
            self._parts[part_id] = PartRecord(
                id=part_id,
                part_number=number,
                name_en=str(payload["name_en"]),
                name_ar=str(payload["name_ar"]),
                description_en=str(payload.get("description_en", "")),
                category=str(payload["category"]),
                unit_of_measure=str(payload["unit_of_measure"]),
                is_active=bool(payload["is_active"]),
                aliases=tuple(sorted(aliases_by_number.get(number, []))),
            )
            self._part_id_by_number[number] = part_id
            self._id_by_number_key[part_number_key(number)] = part_id

        # Configuration id -> compatibility rows, keyed through (brand, model_code, config_code).
        config_id_by_triple: dict[tuple[str, str, str], int] = {}
        for model in self._models:
            for config in model.configurations:
                config_id_by_triple[(model.brand, model.model_code, config.config_code)] = config.id
        self._compat_by_config: dict[int, list[CompatibilityRow]] = defaultdict(list)
        self._machines_by_part: dict[int, list[CompatibleMachine]] = defaultdict(list)
        for record in grouped.get("part_compatibility", []):
            payload = record.payload
            number = str(payload["part_number"])
            triple = (str(payload["brand"]), str(payload["model_code"]), str(payload["config_code"]))
            compat_part_id = self._part_id_by_number.get(number)
            compat_config_id = config_id_by_triple.get(triple)
            if compat_part_id is None or compat_config_id is None:
                continue
            quantity = _as_float(payload["quantity_per_unit"])
            self._compat_by_config[compat_config_id].append(
                CompatibilityRow(compat_part_id, quantity, str(payload["source_reference"]))
            )
            owner = self._model_by_config.get(compat_config_id)
            owned = (
                next((c for c in owner.configurations if c.id == compat_config_id), None) if owner else None
            )
            if owner is not None and owned is not None:
                self._machines_by_part[compat_part_id].append(
                    CompatibleMachine(compat_config_id, owner.brand, owner.model_code, owner.display_name,
                                      owned.config_code, quantity)
                )

        # Forward supersession edges old -> new (single successor per part; validated upstream).
        self._successor: dict[int, int] = {}
        for record in grouped.get("part_supersessions", []):
            old_id = self._part_id_by_number.get(str(record.payload["old_part_number"]))
            new_id = self._part_id_by_number.get(str(record.payload["new_part_number"]))
            if old_id is not None and new_id is not None:
                self._successor.setdefault(old_id, new_id)

        self._warehouses = [
            {"code": str(r.payload["code"]), "name": str(r.payload["name"]), "region": str(r.payload["region"])}
            for r in sorted(grouped.get("warehouses", []), key=lambda r: str(r.payload["code"]))
        ]
        self._transfer_days: dict[tuple[str, str], int] = {
            (str(r.payload["from_code"]), str(r.payload["to_code"])): _as_int(r.payload["transfer_days"])
            for r in grouped.get("warehouse_transfer_routes", [])
        }

    # --- SearchRepository interface --------------------------------------

    async def fetch_models(self) -> list[ModelRecord]:
        return list(self._models)

    async def fetch_model_for_configuration(self, configuration_id: int) -> ModelRecord | None:
        return self._model_by_config.get(configuration_id)

    async def fetch_compatibility(self, configuration_id: int) -> list[CompatibilityRow]:
        return list(self._compat_by_config.get(configuration_id, []))

    async def fetch_supersession_chains(self, part_ids: Sequence[int]) -> dict[int, list[int]]:
        """Map each part to its forward chain ``[part, successor, …]`` with cycle protection (F30)."""
        chains: dict[int, list[int]] = {}
        for origin in part_ids:
            chain = [origin]
            visited = {origin}
            current = origin
            while current in self._successor and len(chain) < MAX_SUPERSESSION_DEPTH:
                current = self._successor[current]
                if current in visited:  # a cycle is never followed into an infinite walk
                    break
                visited.add(current)
                chain.append(current)
            chains[origin] = chain
        return chains

    async def fetch_parts(self, part_ids: Sequence[int]) -> dict[int, PartRecord]:
        return {pid: self._parts[pid] for pid in set(part_ids) if pid in self._parts}

    async def find_part_ids_by_number_keys(self, keys: Sequence[str]) -> dict[str, int]:
        return {key: self._id_by_number_key[key] for key in keys if key in self._id_by_number_key}

    async def fetch_stock(self, part_ids: Sequence[int]) -> dict[int, list[WarehouseStock]]:
        """Netted available per warehouse; a warehouse without a reading reports zero."""
        result: dict[int, list[WarehouseStock]] = {}
        for part_id in set(part_ids):
            by_code = {obs.warehouse_code: obs for obs in self._stock.observations(part_id)}
            result[part_id] = [
                WarehouseStock(
                    w["code"], w["name"], w["region"],
                    by_code[w["code"]].available if w["code"] in by_code else 0,
                )
                for w in self._warehouses
            ]
        return result

    async def fetch_transfer_days(self) -> dict[tuple[str, str], int]:
        return dict(self._transfer_days)

    async def fetch_warehouses(self) -> list[dict[str, str]]:
        return [dict(w) for w in self._warehouses]

    async def fetch_compatible_machines(self, part_id: int, limit: int = 50) -> list[CompatibleMachine]:
        machines = sorted(
            self._machines_by_part.get(part_id, []), key=lambda m: (m.model_code, m.config_code)
        )
        return machines[:limit]

    async def fetch_semantic_similarities(
        self, query_vector: str, model_name: str, part_ids: Sequence[int]
    ) -> dict[int, float]:
        """Injected similarity map; computed ONLY for the given compatible ids (F24).

        A FINITE similarity is clamped to ``[0, 1]`` (cosine on validated unit vectors); a
        non-finite value is passed through UNCHANGED so the service's single F25 NaN check
        rejects it rather than this layer silently masking a miscomputed score.
        """
        similarities: dict[int, float] = {}
        for pid in set(part_ids):
            if pid not in self._semantic:
                continue
            value = self._semantic[pid]
            similarities[pid] = value if (value != value or value in (float("inf"), float("-inf"))) \
                else max(0.0, min(1.0, value))
        return similarities
