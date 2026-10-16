"""Deterministic synthetic catalogue generator. The same seed always produces the same dataset."""

import random
import re
from datetime import date, timedelta

from catalog.blueprint import FAMILIES, TRANSFER_DAYS, WAREHOUSES, FamilySpec, ModelSpec, PartType, ConfigSpec
from catalog.dataset import (
    SCHEMA_VERSION,
    Alias,
    CatalogDataset,
    Compatibility,
    Configuration,
    Family,
    Model,
    Part,
    StockLevel,
    Supersession,
    TransferRoute,
    Warehouse,
)

SERIAL_BLOCK_SIZE = 100_000
SERIALS_PER_CONFIGURATION = 40_000
SERIAL_BASE = 100_000
SUPERSESSION_RATE = 0.08
DOUBLE_SUPERSESSION_COUNT = 3
STOCKOUT_PROBABILITY = 0.25
SUPERSESSION_START = date(2020, 1, 1)
SUPERSESSION_SPAN_DAYS = 6 * 365

_DIGITS = re.compile(r"\d+")


class _PartNumberAllocator:
    """Allocates unique, realistic-looking part numbers per brand prefix and part type."""

    def __init__(self, rng: random.Random) -> None:
        self._rng = rng
        self._used: set[str] = set()

    def allocate(self, prefix: str, code: str) -> str:
        for _ in range(10_000):
            candidate = f"{prefix}-{code}-{self._rng.randint(1000, 9999)}"
            if candidate not in self._used:
                self._used.add(candidate)
                return candidate
        raise RuntimeError(f"Part number space exhausted for {prefix}-{code}")


def _specification(part_type: PartType, rng: random.Random) -> str:
    kind = part_type.spec_kind
    if kind == "spin_on_filter":
        return (f"Spin-on, M{rng.choice([16, 20, 22, 24])}x1.5 thread, "
                f"{rng.randint(90, 260)} mm height, {rng.choice([10, 15, 20, 25])} micron")
    if kind == "element":
        return (f"{rng.randint(120, 480)} mm element, "
                f"{rng.choice(['cellulose', 'synthetic', 'microglass'])} media")
    if kind == "belt":
        return f"Profile {rng.choice(['XPA', 'XPB', 'SPA', 'SPB', '13A', '17A'])}, effective length {rng.randrange(800, 2400, 25)} mm"
    if kind == "hose":
        return f"{rng.choice([38, 45, 50, 63])} mm inner diameter, EPDM, {rng.randint(300, 900)} mm length"
    if kind == "electrical":
        return f"{rng.choice([12, 24, 48])} V, {rng.choice(['IP54', 'IP65', 'IP67'])} rated"
    if kind == "kit":
        return f"Service kit of {rng.randint(3, 14)} components"
    if kind == "tyre":
        return f"{rng.choice(['6.50-10', '7.00-12', '8.25-15', '28x9-15'])} solid press-on"
    return f"Reman-exchange eligible, {rng.randint(1, 18)} kg"


def _quantity(part_type: PartType, model: ModelSpec, config: ConfigSpec) -> float:
    if part_type.quantity_rule == "cylinders":
        match = _DIGITS.search(config.platform)
        if match is None:
            raise ValueError(f"Platform {config.platform} has no cylinder count for {part_type.code}")
        return float(int(match.group()))
    if part_type.quantity_rule == "by_frame":
        return float(part_type.frame_quantities[model.frame])
    return float(part_type.quantity)


def _applies(part_type: PartType, model: ModelSpec) -> bool:
    return part_type.power is None or part_type.power == model.power


def _variance_key(family: FamilySpec, part_type: PartType, model: ModelSpec, config: ConfigSpec) -> tuple[str, ...]:
    if part_type.variance == "platform":
        return (family.code, part_type.code, "platform", config.platform)
    if part_type.variance == "model":
        return (family.code, part_type.code, "model", model.model_code)
    return (family.code, part_type.code, "frame", model.frame)


def _fits_label(part_type: PartType, model: ModelSpec, config: ConfigSpec) -> str:
    if part_type.variance == "platform":
        return f"platform {config.platform}"
    if part_type.variance == "model":
        return f"model {model.model_code}"
    return f"frame {model.frame}"


def generate_catalog(seed: int = 42) -> CatalogDataset:
    """Generate a complete, internally consistent synthetic catalogue."""
    rng = random.Random(seed)
    allocator = _PartNumberAllocator(rng)

    families: list[Family] = []
    models: list[Model] = []
    parts: list[Part] = []
    aliases: list[Alias] = []
    compatibility: list[Compatibility] = []
    part_by_key: dict[tuple[str, ...], str] = {}
    part_type_by_number: dict[str, PartType] = {}

    model_index = 0
    for family in FAMILIES:
        families.append(Family(family.code, family.name_en, family.name_ar))
        for model_spec in family.models:
            serial_base = SERIAL_BASE + model_index * SERIAL_BLOCK_SIZE
            model_index += 1
            configurations = tuple(
                Configuration(
                    config_code=config.config_code,
                    description=config.description,
                    serial_start=serial_base + position * SERIALS_PER_CONFIGURATION,
                    serial_end=serial_base + (position + 1) * SERIALS_PER_CONFIGURATION - 1,
                )
                for position, config in enumerate(model_spec.configurations)
            )
            models.append(Model(family.code, family.brand, model_spec.model_code, model_spec.display_name,
                                model_spec.rated_output, configurations))
            revision = rng.randint(1, 6)

            for config in model_spec.configurations:
                for part_type in family.part_types:
                    if not _applies(part_type, model_spec):
                        continue
                    key = _variance_key(family, part_type, model_spec, config)
                    part_number = part_by_key.get(key)
                    if part_number is None:
                        part_number = allocator.allocate(family.prefix, part_type.code)
                        part_by_key[key] = part_number
                        part_type_by_number[part_number] = part_type
                        parts.append(Part(
                            part_number=part_number,
                            name_en=part_type.name_en,
                            name_ar=part_type.name_ar,
                            description_en=(f"{part_type.name_en} for {family.brand} "
                                            f"{_fits_label(part_type, model_spec, config)}. "
                                            f"{_specification(part_type, rng)}."),
                            category=part_type.category,
                            unit_of_measure="EA",
                            is_active=True,
                        ))
                        aliases.extend(Alias(part_number, alias, "en") for alias in part_type.aliases_en)
                        aliases.extend(Alias(part_number, alias, "ar") for alias in part_type.aliases_ar)
                    compatibility.append(Compatibility(
                        part_number=part_number,
                        brand=family.brand,
                        model_code=model_spec.model_code,
                        config_code=config.config_code,
                        quantity_per_unit=_quantity(part_type, model_spec, config),
                        source_reference=(f"SYNTH-{family.prefix}-PB-{model_spec.model_code} rev {revision}, "
                                          f"section {part_type.category.upper()}"),
                    ))

    supersessions = _generate_supersessions(rng, allocator, parts, part_type_by_number)
    warehouses = tuple(Warehouse(code, name, region) for code, name, region in WAREHOUSES)
    transfer_routes = tuple(
        TransferRoute(origin.code, destination.code, TRANSFER_DAYS[frozenset({origin.code, destination.code})])
        for origin in warehouses
        for destination in warehouses
        if origin.code != destination.code
    )
    stock = _generate_stock(rng, parts, warehouses)

    return CatalogDataset(
        schema_version=SCHEMA_VERSION,
        seed=seed,
        families=tuple(families),
        models=tuple(models),
        parts=tuple(parts),
        aliases=tuple(aliases),
        compatibility=tuple(compatibility),
        supersessions=tuple(supersessions),
        warehouses=warehouses,
        transfer_routes=transfer_routes,
        stock=tuple(stock),
    )


def _generate_supersessions(
    rng: random.Random,
    allocator: _PartNumberAllocator,
    parts: list[Part],
    part_type_by_number: dict[str, PartType],
) -> list[Supersession]:
    """Create inactive predecessor part numbers that customers may still quote."""
    active_parts = [part for part in parts if part.is_active]
    selected = rng.sample(active_parts, k=max(1, int(len(active_parts) * SUPERSESSION_RATE)))
    supersessions: list[Supersession] = []

    for index, current in enumerate(selected):
        chain_length = 2 if index < DOUBLE_SUPERSESSION_COUNT else 1
        successor = current
        newest_date = SUPERSESSION_START + timedelta(days=rng.randint(SUPERSESSION_SPAN_DAYS // 2, SUPERSESSION_SPAN_DAYS))
        for step in range(chain_length):
            prefix, code, _ = successor.part_number.split("-")
            predecessor = Part(
                part_number=allocator.allocate(prefix, code),
                name_en=successor.name_en,
                name_ar=successor.name_ar,
                description_en=f"Superseded. Replaced by {successor.part_number}.",
                category=successor.category,
                unit_of_measure=successor.unit_of_measure,
                is_active=False,
            )
            parts.append(predecessor)
            part_type_by_number[predecessor.part_number] = part_type_by_number[current.part_number]
            effective = newest_date - timedelta(days=step * rng.randint(200, 500))
            supersessions.append(Supersession(
                old_part_number=predecessor.part_number,
                new_part_number=successor.part_number,
                effective_date=effective.isoformat(),
                reason=rng.choice(["Design improvement", "Supplier change", "Material upgrade", "Kit consolidation"]),
            ))
            successor = predecessor
    return supersessions


def _generate_stock(rng: random.Random, parts: list[Part], warehouses: tuple[Warehouse, ...]) -> list[StockLevel]:
    stock: list[StockLevel] = []
    for part in parts:
        if not part.is_active:
            continue
        ceiling = 80 if part.category == "filters" else 30
        for warehouse in warehouses:
            on_hand = 0 if rng.random() < STOCKOUT_PROBABILITY else rng.randint(1, ceiling)
            reserved = rng.randint(0, min(on_hand, 5)) if on_hand and rng.random() < 0.3 else 0
            stock.append(StockLevel(part.part_number, warehouse.code, on_hand, reserved))
    return stock
