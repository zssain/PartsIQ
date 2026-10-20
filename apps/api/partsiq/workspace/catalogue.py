"""Per-workspace catalogue context: the ACTIVE validated version, its search service and stock.

Every workspace (the shared account workspace, or one disposable demo-session workspace) holds
one :class:`CatalogueContext`. It wraps the EXISTING search domain — the validated
:class:`~partsiq.search.repository.CatalogueSnapshotRepository` and the characterized
:class:`~partsiq.search.service.SearchService` — so identification, compatibility filtering,
supersession resolution and fulfilment planning are the same code for both workflow modes, the
review workspace and the catalogue browser. Publishing an import swaps the active version here
(compare-and-set); enquiries bound to the previous version then fail verification as
``STALE_CATALOGUE`` rather than silently mixing versions.

Stock is not a catalogue record. In fixture mode the synthetic seed-42 stock levels are the
stock source; each read is stamped with the time it was observed so the freshness rule
(``stock_max_age_seconds``) and the approval-time stock refresh behave exactly as they would
against a live stock feed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, UUID, uuid5

from partsiq.core.api_models import CatalogueRecord, CatalogueSnapshot
from partsiq.search.repository import (
    CatalogueSnapshotRepository,
    MappingStockSource,
    StockObservation,
)
from partsiq.search.service import SearchService

_EVIDENCE_NS = uuid5(NAMESPACE_URL, "partsiq.catalogue.evidence")


def evidence_id_for(version_id: UUID, source_reference: str) -> UUID:
    """Stable evidence id for a (version, source reference) pair (catalogue_evidence key)."""
    return uuid5(_EVIDENCE_NS, f"{version_id}:{source_reference}")


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass
class VersionRecord:
    """One catalogue version known to a workspace (published / retired / staging)."""

    id: UUID
    label: str
    state: str  # staging | published | retired
    content_sha256: str
    source: str  # fixture | snowflake
    created_at: datetime
    published_at: datetime | None = None
    published_by: UUID | None = None
    import_id: UUID | None = None


@dataclass
class StockLedger:
    """Mutable netted stock per (part_id, warehouse_code) for this workspace.

    ``observe`` returns readings stamped with the current time: each read is a fresh
    observation of the synthetic stock source, which is what an approval-time refresh does.
    """

    levels: dict[int, dict[str, int]] = field(default_factory=dict)
    warehouses: dict[str, tuple[str, str]] = field(default_factory=dict)  # code -> (name, region)

    def observe(self, part_id: int) -> list[StockObservation]:
        observed = _now()
        out = []
        for code, (name, region) in self.warehouses.items():
            out.append(
                StockObservation(code, name, region, max(0, self.levels.get(part_id, {}).get(code, 0)), observed)
            )
        return out


class _LedgerStockSource(MappingStockSource):
    """Adapter so the search repository reads the workspace ledger live (not a frozen copy)."""

    def __init__(self, ledger: StockLedger) -> None:
        super().__init__({})
        self._ledger = ledger

    def observations(self, part_id: int) -> list[StockObservation]:
        return self._ledger.observe(part_id)


@dataclass
class CatalogueContext:
    """The active catalogue version + search service + stock ledger of one workspace."""

    snapshot: CatalogueSnapshot
    stock: StockLedger
    versions: list[VersionRecord]
    repository: CatalogueSnapshotRepository = field(init=False)
    search: SearchService = field(init=False)
    warehouse_codes: list[str] = field(init=False)

    def __post_init__(self) -> None:
        self._rebuild()

    def _rebuild(self) -> None:
        self.repository = CatalogueSnapshotRepository.from_active_snapshot(
            self.snapshot, stock=_LedgerStockSource(self.stock)
        )
        self.search = SearchService(self.repository, None, 0.4, 5)
        self.warehouse_codes = [
            r.entity_key
            for r in self.snapshot.records
            if r.entity_type == "warehouses"
        ]
        for record in self.snapshot.records:
            if record.entity_type == "warehouses":
                self.stock.warehouses.setdefault(
                    record.entity_key,
                    (str(record.payload.get("name", record.entity_key)), str(record.payload.get("region", ""))),
                )

    # --- identity -------------------------------------------------------------

    @property
    def version_id(self) -> UUID:
        return self.snapshot.version_id

    @property
    def source(self) -> str:
        return str(self.snapshot.source)

    def warehouse_id(self, code: str) -> int:
        """1-based warehouse id in load order (matches the seed-42 ``warehouses`` ordinals)."""
        return self.warehouse_codes.index(code) + 1

    def warehouse_code(self, warehouse_id: int) -> str | None:
        if 1 <= warehouse_id <= len(self.warehouse_codes):
            return self.warehouse_codes[warehouse_id - 1]
        return None

    def warehouse_name(self, warehouse_id: int) -> str:
        code = self.warehouse_code(warehouse_id)
        if code is None:
            return f"Warehouse {warehouse_id}"
        return self.stock.warehouses.get(code, (code, ""))[0]

    # --- record access ----------------------------------------------------------

    def records_of(self, entity_type: str) -> list[CatalogueRecord]:
        return [r for r in self.snapshot.records if r.entity_type == entity_type]

    def part_payload(self, part_id: int) -> dict | None:
        for record in self.snapshot.records:
            if record.entity_type == "parts" and str(record.payload.get("id")) == str(part_id):
                return dict(record.payload)
        return None

    def part_by_number(self, part_number: str) -> dict | None:
        key = part_number.strip().upper()
        for record in self.snapshot.records:
            if record.entity_type == "parts" and str(record.payload.get("part_number", "")).upper() == key:
                return dict(record.payload)
        return None

    def activate(self, snapshot: CatalogueSnapshot, *, published_by: UUID | None, import_id: UUID | None, label: str) -> VersionRecord:
        """Swap the active version (caller already performed the compare-and-set)."""
        now = _now()
        for version in self.versions:
            if version.state == "published":
                version.state = "retired"
        record = VersionRecord(
            id=snapshot.version_id,
            label=label,
            state="published",
            content_sha256=snapshot.content_sha256,
            source=str(snapshot.source),
            created_at=now,
            published_at=now,
            published_by=published_by,
            import_id=import_id,
        )
        self.versions.append(record)
        self.snapshot = snapshot
        self._rebuild()
        return record


def seed_stock(snapshot: CatalogueSnapshot) -> StockLedger:
    """Build the synthetic stock ledger for a fixture workspace from the seed-42 dataset."""
    from partsiq.catalogue import fixtures as fx

    dataset = fx.generate_dataset(fx.DEFAULT_SEED)
    ordinals = fx.part_ordinals(dataset)
    ledger = StockLedger()
    for warehouse in dataset.warehouses:
        ledger.warehouses[warehouse.code] = (warehouse.name, warehouse.region)
    for level in dataset.stock:
        part_id = ordinals.get(level.part_number)
        if part_id is None:
            continue
        net = level.quantity_on_hand - level.quantity_reserved
        ledger.levels.setdefault(part_id, {})[level.warehouse_code] = max(0, int(net))
    return ledger


def fixture_catalogue_context(snapshot: CatalogueSnapshot) -> CatalogueContext:
    """A fresh catalogue context over the committed seed-42 snapshot (one per workspace)."""
    version = VersionRecord(
        id=snapshot.version_id,
        label="seed-42 synthetic catalogue",
        state="published",
        content_sha256=snapshot.content_sha256,
        source=str(snapshot.source),
        created_at=datetime(2026, 10, 11, tzinfo=timezone.utc),
        published_at=datetime(2026, 10, 11, tzinfo=timezone.utc),
    )
    return CatalogueContext(snapshot=snapshot, stock=seed_stock(snapshot), versions=[version])
