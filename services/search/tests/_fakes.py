"""In-memory fakes for search tests.

These implement the SearchRepository method surface with hand-built records, so the
SearchService use cases (compatibility gate, ranking, margin, supersession) can be
exercised deterministically WITHOUT a database. Real asyncpg behaviour is integration
work; here we pin the domain logic the prompts specify.
"""
from __future__ import annotations

import math

from app.fulfilment import WarehouseStock
from app.identification import ConfigurationRecord, ModelRecord
from app.repository import CompatibilityRow, CompatibleMachine, PartRecord

CONFIG_ID = 100

MODEL = ModelRecord(
    id=1, brand="Veltrano", model_code="VP-20", display_name="Veltrano VP-20",
    rated_output="20 kVA", family_code="GENSET", family_name_en="Generator", family_name_ar="مولد",
    configurations=(ConfigurationRecord(CONFIG_ID, "A", "Config A", 100000, 199999),),
)

# part_id -> PartRecord
_PARTS: dict[int, PartRecord] = {
    1: PartRecord(1, "VP-OF-1", "oil filter", "فلتر زيت", "", "filters", "EA", True, ()),
    2: PartRecord(2, "VP-FF-2", "fuel filter", "فلتر وقود", "", "filters", "EA", True, ()),
    3: PartRecord(3, "VP-FS-3", "fuel water separator", "فاصل ماء وقود", "", "filters", "EA", True, ()),
    4: PartRecord(4, "VP-HF-4", "hydraulic filter", "فلتر هيدروليك", "", "filters", "EA", True, ()),
    5: PartRecord(5, "VP-OLD-5", "old oil filter", "فلتر زيت قديم", "", "filters", "EA", False, ()),
    6: PartRecord(6, "VP-NEW-6", "oil filter mk2", "فلتر زيت ٢", "", "filters", "EA", True, ()),
    7: PartRecord(7, "VP-OLD-7", "old belt", "سير قديم", "", "belts", "EA", False, ()),
    8: PartRecord(8, "VP-NEW-8", "belt mk2", "سير ٢", "", "belts", "EA", True, ()),
}

# forward supersession chains (origin -> [origin, successor, ...])
_CHAINS: dict[int, list[int]] = {5: [5, 6], 7: [7, 8]}


class FakeRepository:
    def __init__(self, *, compatibility: list[CompatibilityRow], semantic: dict[int, float] | None = None) -> None:
        self._compat = compatibility
        self._semantic = semantic or {}

    async def fetch_models(self) -> list[ModelRecord]:
        return [MODEL]

    async def fetch_model_for_configuration(self, configuration_id: int) -> ModelRecord | None:
        return MODEL if configuration_id == CONFIG_ID else None

    async def fetch_compatibility(self, configuration_id: int) -> list[CompatibilityRow]:
        return list(self._compat) if configuration_id == CONFIG_ID else []

    async def fetch_supersession_chains(self, part_ids) -> dict[int, list[int]]:
        return {pid: list(_CHAINS.get(pid, [pid])) for pid in part_ids}

    async def find_part_ids_by_number_keys(self, keys) -> dict[str, int]:
        by_key = {p.part_number.replace("-", ""): pid for pid, p in _PARTS.items()}
        return {key: by_key[key] for key in keys if key in by_key}

    async def fetch_parts(self, part_ids) -> dict[int, PartRecord]:
        return {pid: _PARTS[pid] for pid in set(part_ids) if pid in _PARTS}

    async def fetch_stock(self, part_ids) -> dict[int, list[WarehouseStock]]:
        return {
            pid: [
                WarehouseStock("JED", "Jeddah", "Western", 5 if pid == 1 else 0),
                WarehouseStock("RUH", "Riyadh", "Central", 10),
            ]
            for pid in set(part_ids)
        }

    async def fetch_semantic_similarities(self, query_vector, model_name, part_ids) -> dict[int, float]:
        return {pid: self._semantic[pid] for pid in part_ids if pid in self._semantic}

    async def fetch_transfer_days(self) -> dict[tuple[str, str], int]:
        return {("RUH", "JED"): 2, ("JED", "RUH"): 2}

    async def fetch_warehouses(self):
        return [
            {"code": "JED", "name": "Jeddah", "region": "Western"},
            {"code": "RUH", "name": "Riyadh", "region": "Central"},
        ]

    async def fetch_compatible_machines(self, part_id, limit: int = 50) -> list[CompatibleMachine]:
        return [CompatibleMachine(CONFIG_ID, "Veltrano", "VP-20", "Veltrano VP-20", "A", 1.0)]


def full_compatibility() -> list[CompatibilityRow]:
    """Parts 1,2,3 directly compatible; 5->6 (6 has its own fitment); 7->8 (8 does NOT).

    Part 4 (hydraulic) is active but has NO fitment row (compatibility-gate test).
    """
    return [
        CompatibilityRow(1, 1.0, "SRC-1 p1"),
        CompatibilityRow(2, 1.0, "SRC-2 p1"),
        CompatibilityRow(3, 1.0, "SRC-3 p1"),
        CompatibilityRow(5, 1.0, "SRC-5 p1"),  # old oil filter, supersedes to 6
        CompatibilityRow(6, 1.0, "SRC-6 p1"),  # successor has its OWN fitment -> offered
        CompatibilityRow(7, 1.0, "SRC-7 p1"),  # old belt, supersedes to 8 (8 has no row -> rejected)
    ]


NAN = math.nan


class FakeProvider:
    """Stand-in embedding provider: returns fixed 1024-d vectors without loading BGE-M3."""

    model_name = "BAAI/bge-m3"

    def __init__(self, dimension: int = 1024) -> None:
        self._dimension = dimension

    def embed(self, texts):
        return [[0.03125] * self._dimension for _ in texts]
