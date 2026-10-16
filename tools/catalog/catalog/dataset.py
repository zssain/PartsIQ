"""Portable catalogue dataset format. Records reference each other by natural keys, not database IDs."""

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, TypeVar

SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class Family:
    code: str
    name_en: str
    name_ar: str


@dataclass(frozen=True, slots=True)
class Configuration:
    config_code: str
    description: str
    serial_start: int
    serial_end: int


@dataclass(frozen=True, slots=True)
class Model:
    family_code: str
    brand: str
    model_code: str
    display_name: str
    rated_output: str
    configurations: tuple[Configuration, ...]


@dataclass(frozen=True, slots=True)
class Part:
    part_number: str
    name_en: str
    name_ar: str
    description_en: str
    category: str
    unit_of_measure: str
    is_active: bool


@dataclass(frozen=True, slots=True)
class Alias:
    part_number: str
    alias: str
    language: str


@dataclass(frozen=True, slots=True)
class Compatibility:
    part_number: str
    brand: str
    model_code: str
    config_code: str
    quantity_per_unit: float
    source_reference: str


@dataclass(frozen=True, slots=True)
class Supersession:
    old_part_number: str
    new_part_number: str
    effective_date: str
    reason: str


@dataclass(frozen=True, slots=True)
class Warehouse:
    code: str
    name: str
    region: str


@dataclass(frozen=True, slots=True)
class TransferRoute:
    from_code: str
    to_code: str
    transfer_days: int


@dataclass(frozen=True, slots=True)
class StockLevel:
    part_number: str
    warehouse_code: str
    quantity_on_hand: int
    quantity_reserved: int


@dataclass(frozen=True, slots=True)
class CatalogDataset:
    schema_version: int
    seed: int
    families: tuple[Family, ...]
    models: tuple[Model, ...]
    parts: tuple[Part, ...]
    aliases: tuple[Alias, ...]
    compatibility: tuple[Compatibility, ...]
    supersessions: tuple[Supersession, ...]
    warehouses: tuple[Warehouse, ...]
    transfer_routes: tuple[TransferRoute, ...]
    stock: tuple[StockLevel, ...]

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def from_json(cls, raw: str) -> "CatalogDataset":
        data = json.loads(raw)
        if data.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"Unsupported dataset schema version: {data.get('schema_version')}")
        return cls(
            schema_version=data["schema_version"],
            seed=data["seed"],
            families=_records(Family, data["families"]),
            models=tuple(
                Model(
                    **{key: value for key, value in model.items() if key != "configurations"},
                    configurations=_records(Configuration, model["configurations"]),
                )
                for model in data["models"]
            ),
            parts=_records(Part, data["parts"]),
            aliases=_records(Alias, data["aliases"]),
            compatibility=_records(Compatibility, data["compatibility"]),
            supersessions=_records(Supersession, data["supersessions"]),
            warehouses=_records(Warehouse, data["warehouses"]),
            transfer_routes=_records(TransferRoute, data["transfer_routes"]),
            stock=_records(StockLevel, data["stock"]),
        )

    @classmethod
    def read(cls, path: Path) -> "CatalogDataset":
        return cls.from_json(path.read_text(encoding="utf-8"))


RecordT = TypeVar("RecordT")


def _records(record_type: type[RecordT], items: list[dict[str, Any]]) -> tuple[RecordT, ...]:
    allowed = {field.name for field in fields(record_type)}  # type: ignore[arg-type]
    result = []
    for item in items:
        unknown = set(item) - allowed
        if unknown:
            raise ValueError(f"Unknown fields for {record_type.__name__}: {sorted(unknown)}")
        result.append(record_type(**item))
    return tuple(result)
