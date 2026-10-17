"""Foundation 05 — deterministic synthetic catalogue + the four demo scenarios.

This module is the single-package home for the demo data generator that was previously
spread across ``tools/catalog`` and ``tools/demo`` in the legacy build. It is fully
self-contained (no import from ``tools/``) and produces the SAME typed
:class:`~partsiq.core.api_models.CatalogueSnapshot` /
:class:`~partsiq.core.api_models.CatalogueRecord` shape that foundation 02 defined, so the
committed fixture loads straight through :class:`FixtureCatalogueRepository`.

Determinism
-----------
Seed 42 (``DEFAULT_SEED``) deterministically produces one fixed dataset. Regenerating with the
same seed yields byte-identical ``fixtures/catalogue.json`` and ``fixtures/scenarios.json``
(``test_05_fixtures.py`` asserts the committed files equal a fresh generation). The
``version_id`` is derived deterministically from the content digest (UUIDv5), so it never
drifts between runs.

Database ids == 1-based load ordinals
-------------------------------------
The catalogue loader inserts records in dataset order under ``RESTART IDENTITY``, so a part's
database SERIAL id is its 1-based ordinal in ``dataset.parts`` and a configuration's id is its
1-based ordinal across models in load order (``catalogue/loader.py``). The catalogue RECORDS
carry those ordinals as ``entity_key`` for ``parts`` / ``model_configurations``, and the
:class:`~partsiq.core.contracts.DemoScenario` cases reference the SAME ordinals in
``expected_part_ids`` / ``expected_configuration_id``. The controlled seed transaction assigns
the identical ids on load, so a scenario resolved against the serving database matches the
fixture exactly.

Synthetic, never real client data
----------------------------------
Every brand, model, platform and part number is fictional. The snapshot carries a
``catalogue_meta`` record (``entity_type`` outside the catalogue entity set is NOT used; the
marker lives on the generated :class:`CatalogueBuild`), and every scenario text is synthetic.
``fixtures/README.md`` records the provenance. No fixture inserts an approved recommendation.

Refusal
-------
:func:`build_scenarios` and :func:`validate_scenarios` REFUSE to emit a scenario the catalogue
cannot demonstrate: an ``incompatible_number`` whose expected part is actually compatible, or a
``local_shortage`` whose stock claim is unsupported, raises :class:`ScenarioError` / surfaces a
validation error rather than shipping a lie (F02).
"""
from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Literal
from uuid import UUID

from partsiq.core.api_models import CatalogueRecord, CatalogueSnapshot, DemoScenario

from .models import build_snapshot, content_sha256

# --------------------------------------------------------------------------- constants

DEFAULT_SEED = 42

#: Fixed UUID namespace for deriving a deterministic ``version_id`` from the content digest.
_VERSION_NAMESPACE = UUID("5e1d0005-0000-4000-8000-000000000005")

#: Repository root → ``fixtures/`` output directory for the committed artefacts.
_REPO_ROOT = Path(__file__).resolve().parents[4]
FIXTURES_DIR = _REPO_ROOT / "fixtures"
CATALOGUE_PATH = FIXTURES_DIR / "catalogue.json"
SCENARIOS_PATH = FIXTURES_DIR / "scenarios.json"

_SCENARIO_IDS: frozenset[str] = frozenset(
    {"mixed_photo", "missing_serial", "incompatible_number", "local_shortage"}
)

_DIGITS = re.compile(r"\d+")
_ARABIC = re.compile("[؀-ۿ]")

# Synthetic generation knobs (ported verbatim from the legacy seed-42 generator).
SERIAL_BLOCK_SIZE = 100_000
SERIALS_PER_CONFIGURATION = 40_000
SERIAL_BASE = 100_000
SUPERSESSION_RATE = 0.08
DOUBLE_SUPERSESSION_COUNT = 3
STOCKOUT_PROBABILITY = 0.25
SUPERSESSION_START = date(2020, 1, 1)
SUPERSESSION_SPAN_DAYS = 6 * 365


class ScenarioError(ValueError):
    """Raised when the generated catalogue cannot demonstrate a required scenario."""


# --------------------------------------------------------------------------- blueprint

Variance = Literal["platform", "model", "frame"]
PowerSource = Literal["diesel", "electric"]
QuantityRule = Literal["fixed", "cylinders", "by_frame"]
SpecKind = Literal[
    "spin_on_filter", "element", "belt", "hose", "electrical", "kit", "mechanical", "tyre"
]


@dataclass(frozen=True, slots=True)
class PartType:
    code: str
    name_en: str
    name_ar: str
    category: str
    variance: Variance
    spec_kind: SpecKind
    aliases_en: tuple[str, ...] = ()
    aliases_ar: tuple[str, ...] = ()
    power: PowerSource | None = None
    quantity: int = 1
    quantity_rule: QuantityRule = "fixed"
    frame_quantities: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ConfigSpec:
    config_code: str
    description: str
    platform: str


@dataclass(frozen=True, slots=True)
class ModelSpec:
    model_code: str
    display_name: str
    rated_output: str
    frame: str
    power: PowerSource
    configurations: tuple[ConfigSpec, ...]


@dataclass(frozen=True, slots=True)
class FamilySpec:
    code: str
    name_en: str
    name_ar: str
    brand: str
    prefix: str
    models: tuple[ModelSpec, ...]
    part_types: tuple[PartType, ...]


def _oil_filter(variance: Variance, power: PowerSource | None = "diesel") -> PartType:
    return PartType(
        "OF", "Oil filter", "فلتر زيت", "filters", variance, "spin_on_filter",
        ("lube filter", "engine oil filter"), ("فلتر الزيت", "فلتر زيت المكينة"), power=power,
    )


def _fuel_filter(variance: Variance) -> PartType:
    return PartType(
        "FF", "Fuel filter", "فلتر وقود", "filters", variance, "spin_on_filter",
        ("diesel filter",), ("فلتر ديزل", "فلتر الديزل", "فلتر الوقود"), power="diesel",
    )


def _water_separator(variance: Variance) -> PartType:
    return PartType(
        "WS", "Fuel water separator", "فاصل الماء عن الوقود", "filters", variance, "element",
        ("water separator", "sedimenter", "primary fuel filter"),
        ("فاصل الماء", "فلتر الماء"), power="diesel",
    )


def _air_filter(variance: Variance, power: PowerSource | None = None) -> PartType:
    return PartType(
        "AF", "Air filter element", "فلتر هواء", "filters", variance, "element",
        ("air cleaner", "air element"), ("فلتر الهواء", "فلتر هوا"), power=power,
    )


def _belt(variance: Variance, power: PowerSource | None = None) -> PartType:
    return PartType(
        "FB", "Fan belt", "سير المروحة", "belts", variance, "belt",
        ("v belt", "drive belt"), ("سير", "سير المروحه", "سير الدينامو"), power=power,
    )


def _hydraulic_filter(variance: Variance) -> PartType:
    return PartType(
        "HF", "Hydraulic filter", "فلتر هيدروليك", "filters", variance, "element",
        ("hydraulic return filter", "hydraulic oil filter"), ("فلتر الهيدروليك",),
    )


_GENERATORS = FamilySpec(
    code="GENSET", name_en="Diesel generators", name_ar="مولدات كهربائية",
    brand="Veltrano Power", prefix="VP",
    models=(
        ModelSpec("VP-20", "VP-20 Diesel Generator", "20 kVA", "S", "diesel", (
            ConfigSpec("A", "VD3 engine, mechanical governor", "VD3"),
            ConfigSpec("B", "VD3E engine, electronic governor", "VD3E"),
        )),
        ModelSpec("VP-60", "VP-60 Diesel Generator", "60 kVA", "S", "diesel", (
            ConfigSpec("A", "VD4 engine", "VD4"),
            ConfigSpec("B", "VD4T turbocharged engine", "VD4T"),
        )),
        ModelSpec("VP-100", "VP-100 Diesel Generator", "100 kVA", "M", "diesel", (
            ConfigSpec("A", "VD4T turbocharged engine", "VD4T"),
            ConfigSpec("B", "VD6 engine", "VD6"),
        )),
        ModelSpec("VP-250", "VP-250 Diesel Generator", "250 kVA", "M", "diesel", (
            ConfigSpec("A", "VD6T turbocharged engine", "VD6T"),
        )),
        ModelSpec("VP-500", "VP-500 Diesel Generator", "500 kVA", "L", "diesel", (
            ConfigSpec("A", "VD12 engine", "VD12"),
            ConfigSpec("B", "VD12T turbocharged engine", "VD12T"),
        )),
    ),
    part_types=(
        _oil_filter("platform"),
        _fuel_filter("platform"),
        _water_separator("platform"),
        _air_filter("frame"),
        _belt("platform"),
        PartType("RH", "Radiator hose", "خرطوم الرديتر", "cooling", "model", "hose",
                 ("coolant hose", "top hose"), ("خرطوم الماء", "لي الرديتر")),
        PartType("WP", "Water pump", "طرمبة ماء", "cooling", "platform", "mechanical",
                 ("coolant pump",), ("مضخة مياه", "طرمبة موية", "طرمبة الماء")),
        PartType("TS", "Thermostat", "ثرموستات", "cooling", "platform", "mechanical",
                 ("coolant thermostat",), ("ثيرموستات", "بلف الحرارة")),
        PartType("SM", "Starter motor", "سلف", "electrical", "platform", "electrical",
                 ("starter", "self starter"), ("محرك بدء التشغيل", "سلف المكينة")),
        PartType("AV", "Automatic voltage regulator", "منظم الجهد الآلي", "electrical", "frame",
                 "electrical", ("avr", "voltage regulator"), ("منظم جهد", "منظم الفولت")),
        PartType("GK", "Top end gasket kit", "طقم جوانات", "engine", "platform", "kit",
                 ("head gasket kit", "gasket set"), ("جوانات راس", "طقم جوان")),
        PartType("FI", "Fuel injector", "بخاخ وقود", "engine", "platform", "mechanical",
                 ("injector", "injector nozzle"), ("بخاخ", "بخاخات", "بخاخ ديزل"),
                 quantity_rule="cylinders"),
    ),
)

_COMPRESSORS = FamilySpec(
    code="COMPRESSOR", name_en="Air compressors", name_ar="ضواغط هواء",
    brand="Corvane Air", prefix="CA",
    models=(
        ModelSpec("CA-37", "CA-37 Rotary Screw Compressor", "37 kW", "S", "electric", (
            ConfigSpec("A", "Air-cooled, 8 bar", "CE37-8"),
            ConfigSpec("B", "Air-cooled, 10 bar", "CE37-10"),
        )),
        ModelSpec("CA-75", "CA-75 Rotary Screw Compressor", "75 kW", "M", "electric", (
            ConfigSpec("A", "Air-cooled, 8 bar", "CE75-8"),
        )),
        ModelSpec("CA-110", "CA-110 Rotary Screw Compressor", "110 kW", "M", "electric", (
            ConfigSpec("A", "Water-cooled, 8 bar", "CE110-W"),
            ConfigSpec("B", "Air-cooled, 8 bar", "CE110-A"),
        )),
        ModelSpec("CP-185", "CP-185 Portable Diesel Compressor", "185 cfm", "P", "diesel", (
            ConfigSpec("A", "VD4 diesel drive", "CPD4"),
        )),
        ModelSpec("CP-375", "CP-375 Portable Diesel Compressor", "375 cfm", "P", "diesel", (
            ConfigSpec("A", "VD6 diesel drive", "CPD6"),
        )),
    ),
    part_types=(
        PartType("OF", "Compressor oil filter", "فلتر زيت الكمبروسر", "filters", "frame",
                 "spin_on_filter", ("oil filter", "lube filter"), ("فلتر زيت", "فلتر الزيت")),
        _air_filter("frame"),
        _fuel_filter("platform"),
        PartType("SE", "Air oil separator element", "فاصل الزيت والهواء", "filters", "model",
                 "element", ("separator", "oil separator", "separator element"),
                 ("فاصل زيت", "سبريتر", "فلتر السبريتر")),
        PartType("IV", "Intake valve kit", "طقم صمام السحب", "valves", "frame", "kit",
                 ("inlet valve kit", "unloader kit"), ("صمام سحب", "طقم بلف السحب")),
        PartType("MV", "Minimum pressure valve kit", "طقم صمام الضغط الأدنى", "valves", "frame",
                 "kit", ("mpv kit", "minimum pressure valve"), ("بلف الضغط", "صمام الضغط")),
        _belt("model"),
        PartType("TS", "Discharge temperature sensor", "حساس حرارة", "electrical", "model",
                 "electrical", ("temp sensor", "temperature probe"),
                 ("حساس الحرارة", "سنسر حرارة")),
    ),
)

_FORKLIFTS = FamilySpec(
    code="FORKLIFT", name_en="Forklift trucks", name_ar="رافعات شوكية",
    brand="Halvorn Lift", prefix="HL",
    models=(
        ModelSpec("HL-25D", "HL-25D Diesel Forklift", "2.5 t", "S", "diesel", (
            ConfigSpec("A", "Duplex mast, 3.0 m lift", "HL25-DUP"),
            ConfigSpec("B", "Triplex mast, 4.5 m lift", "HL25-TPX"),
        )),
        ModelSpec("HL-30D", "HL-30D Diesel Forklift", "3.0 t", "S", "diesel", (
            ConfigSpec("A", "Duplex mast, 3.0 m lift", "HL30-DUP"),
        )),
        ModelSpec("HL-50D", "HL-50D Diesel Forklift", "5.0 t", "M", "diesel", (
            ConfigSpec("A", "Duplex mast, 3.0 m lift", "HL50-DUP"),
            ConfigSpec("B", "Triplex mast, 5.0 m lift", "HL50-TPX"),
        )),
        ModelSpec("HL-25E", "HL-25E Electric Forklift", "2.5 t", "E", "electric", (
            ConfigSpec("A", "48 V, duplex mast, 3.0 m lift", "HL25E-DUP"),
        )),
        ModelSpec("HL-70D", "HL-70D Diesel Forklift", "7.0 t", "L", "diesel", (
            ConfigSpec("A", "Duplex mast, 3.5 m lift", "HL70-DUP"),
        )),
    ),
    part_types=(
        _oil_filter("frame"),
        _fuel_filter("frame"),
        _air_filter("frame", power="diesel"),
        _hydraulic_filter("frame"),
        PartType("MC", "Mast lift chain", "سلسلة الصاري", "mast", "platform", "mechanical",
                 ("lift chain", "mast chain"), ("جنزير", "جنزير الرافعة", "جنزير الكلارك"),
                 quantity=2),
        PartType("BP", "Brake shoe set", "طقم فحمات فرامل", "brakes", "frame", "kit",
                 ("brake pads", "brake shoes"), ("فحمات", "فحمات فرامل", "فحمات الكلارك")),
        PartType("TY", "Drive tyre", "إطار القيادة", "wheels", "model", "tyre",
                 ("front tyre", "front tire", "solid tyre"), ("كفر", "تاير", "كفر امامي"),
                 quantity=2),
        PartType("BT", "Traction battery", "بطارية الجر", "electrical", "model", "electrical",
                 ("forklift battery", "traction battery pack"), ("بطارية", "بطارية الكلارك"),
                 power="electric"),
    ),
)

_EXCAVATORS = FamilySpec(
    code="EXCAVATOR", name_en="Crawler excavators", name_ar="حفارات",
    brand="Duneforge", prefix="DF",
    models=(
        ModelSpec("DF-140", "DF-140 Crawler Excavator", "14 t", "S", "diesel", (
            ConfigSpec("A", "DE4 Tier 3 engine", "DE4"),
            ConfigSpec("B", "DE4V Stage V engine", "DE4V"),
        )),
        ModelSpec("DF-210", "DF-210 Crawler Excavator", "21 t", "M", "diesel", (
            ConfigSpec("A", "DE6 Tier 3 engine", "DE6"),
            ConfigSpec("B", "DE6V Stage V engine", "DE6V"),
        )),
        ModelSpec("DF-300", "DF-300 Crawler Excavator", "30 t", "L", "diesel", (
            ConfigSpec("A", "DE6H Tier 3 engine", "DE6H"),
        )),
        ModelSpec("DF-360", "DF-360 Crawler Excavator", "36 t", "L", "diesel", (
            ConfigSpec("A", "DE7V Stage V engine", "DE7V"),
        )),
    ),
    part_types=(
        _oil_filter("platform"),
        _fuel_filter("platform"),
        _water_separator("platform"),
        _air_filter("frame"),
        _hydraulic_filter("frame"),
        _belt("platform"),
        PartType("TH", "Bucket tooth", "سن البكت", "ground engaging", "frame", "mechanical",
                 ("bucket tip", "tooth point"), ("سن الشيول", "سنون البكت", "اسنان البكت"),
                 quantity_rule="by_frame", frame_quantities={"S": 5, "M": 5, "L": 6}),
        PartType("TR", "Track roller", "بكرة الجنزير", "undercarriage", "frame", "mechanical",
                 ("bottom roller", "lower roller"), ("بكرة", "رولة الجنزير", "بكرات الجنزير"),
                 quantity_rule="by_frame", frame_quantities={"S": 14, "M": 16, "L": 18}),
        PartType("TA", "Track adjuster seal kit", "طقم جلود شداد الجنزير", "undercarriage",
                 "frame", "kit", ("track tensioner seal kit", "recoil seal kit"),
                 ("جلود الشداد", "طقم شداد الجنزير")),
    ),
)

FAMILIES: tuple[FamilySpec, ...] = (_GENERATORS, _COMPRESSORS, _FORKLIFTS, _EXCAVATORS)

WAREHOUSES: tuple[tuple[str, str, str], ...] = (
    ("JED", "Western Regional Warehouse (Jeddah)", "Western"),
    ("RUH", "Central Regional Warehouse (Riyadh)", "Central"),
    ("DMM", "Eastern Regional Warehouse (Dammam)", "Eastern"),
)

# Symmetric synthetic planning lead times in days.
TRANSFER_DAYS: dict[frozenset[str], int] = {
    frozenset({"JED", "RUH"}): 2,
    frozenset({"RUH", "DMM"}): 1,
    frozenset({"JED", "DMM"}): 3,
}


# --------------------------------------------------------------------------- dataset

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
class CatalogueDataset:
    """Portable synthetic dataset; records reference each other by natural keys."""

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


# --------------------------------------------------------------------------- generator

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
        return (f"Profile {rng.choice(['XPA', 'XPB', 'SPA', 'SPB', '13A', '17A'])}, "
                f"effective length {rng.randrange(800, 2400, 25)} mm")
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


def _variance_key(
    family: FamilySpec, part_type: PartType, model: ModelSpec, config: ConfigSpec
) -> tuple[str, ...]:
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


def generate_dataset(seed: int = DEFAULT_SEED) -> CatalogueDataset:
    """Generate a complete, internally consistent synthetic catalogue. Deterministic by seed."""
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
            models.append(Model(family.code, family.brand, model_spec.model_code,
                                 model_spec.display_name, model_spec.rated_output, configurations))
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
        TransferRoute(origin.code, destination.code,
                      TRANSFER_DAYS[frozenset({origin.code, destination.code})])
        for origin in warehouses
        for destination in warehouses
        if origin.code != destination.code
    )
    stock = _generate_stock(rng, parts, warehouses)

    return CatalogueDataset(
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
        newest_date = SUPERSESSION_START + timedelta(
            days=rng.randint(SUPERSESSION_SPAN_DAYS // 2, SUPERSESSION_SPAN_DAYS)
        )
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
                reason=rng.choice(["Design improvement", "Supplier change",
                                   "Material upgrade", "Kit consolidation"]),
            ))
            successor = predecessor
    return supersessions


def _generate_stock(
    rng: random.Random, parts: list[Part], warehouses: tuple[Warehouse, ...]
) -> list[StockLevel]:
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


# --------------------------------------------------------------------------- records

def part_ordinals(dataset: CatalogueDataset) -> dict[str, int]:
    """part_number -> 1-based insertion ordinal (== the loaded SERIAL id)."""
    return {part.part_number: index + 1 for index, part in enumerate(dataset.parts)}


def configuration_ordinals(dataset: CatalogueDataset) -> dict[tuple[str, str, str], int]:
    """(brand, model_code, config_code) -> 1-based ordinal across models in load order."""
    ordinals: dict[tuple[str, str, str], int] = {}
    index = 0
    for model in dataset.models:
        for config in model.configurations:
            index += 1
            ordinals[(model.brand, model.model_code, config.config_code)] = index
    return ordinals


def _entity_key(parts: list[object]) -> str:
    """Composite natural key rendered as compact JSON (matches the foundation 02 fixture shape)."""
    return json.dumps(parts, ensure_ascii=False, separators=(",", ":"))


def dataset_to_records(dataset: CatalogueDataset) -> list[CatalogueRecord]:
    """Project the dataset into the nine-entity-type :class:`CatalogueRecord` shape.

    ``parts`` and ``model_configurations`` are keyed by their 1-based load ordinal (the database
    SERIAL id); every other entity uses its natural key. Stock is deliberately NOT emitted as a
    catalogue RECORD — it lives in a dedicated snapshot table (``catalogue/models.py``).
    """
    part_ids = part_ordinals(dataset)
    config_ids = configuration_ordinals(dataset)
    records: list[CatalogueRecord] = []

    for family in dataset.families:
        records.append(CatalogueRecord(
            entity_type="equipment_families",
            entity_key=family.code,
            payload={"code": family.code, "name_en": family.name_en, "name_ar": family.name_ar},
        ))
    for model in dataset.models:
        records.append(CatalogueRecord(
            entity_type="equipment_models",
            entity_key=_entity_key([model.brand, model.model_code]),
            payload={
                "family_code": model.family_code,
                "brand": model.brand,
                "model_code": model.model_code,
                "display_name": model.display_name,
                "rated_output": model.rated_output,
            },
        ))
        for config in model.configurations:
            config_id = config_ids[(model.brand, model.model_code, config.config_code)]
            records.append(CatalogueRecord(
                entity_type="model_configurations",
                entity_key=str(config_id),
                payload={
                    "id": config_id,
                    "brand": model.brand,
                    "model_code": model.model_code,
                    "config_code": config.config_code,
                    "description": config.description,
                    "serial_start": config.serial_start,
                    "serial_end": config.serial_end,
                },
            ))
    for part in dataset.parts:
        part_id = part_ids[part.part_number]
        records.append(CatalogueRecord(
            entity_type="parts",
            entity_key=str(part_id),
            payload={
                "id": part_id,
                "part_number": part.part_number,
                "name_en": part.name_en,
                "name_ar": part.name_ar,
                "description_en": part.description_en,
                "category": part.category,
                "unit_of_measure": part.unit_of_measure,
                "is_active": part.is_active,
            },
        ))
    for index, alias in enumerate(dataset.aliases, start=1):
        records.append(CatalogueRecord(
            entity_type="part_aliases",
            entity_key=str(index),
            payload={
                "part_number": alias.part_number,
                "alias": alias.alias,
                "language": alias.language,
            },
        ))
    for compat in dataset.compatibility:
        records.append(CatalogueRecord(
            entity_type="part_compatibility",
            entity_key=_entity_key(
                [compat.part_number, compat.brand, compat.model_code, compat.config_code]
            ),
            payload={
                "part_number": compat.part_number,
                "brand": compat.brand,
                "model_code": compat.model_code,
                "config_code": compat.config_code,
                "quantity_per_unit": compat.quantity_per_unit,
                "source_reference": compat.source_reference,
            },
        ))
    for supersession in dataset.supersessions:
        records.append(CatalogueRecord(
            entity_type="part_supersessions",
            entity_key=_entity_key([supersession.old_part_number, supersession.new_part_number]),
            payload={
                "old_part_number": supersession.old_part_number,
                "new_part_number": supersession.new_part_number,
                "effective_date": supersession.effective_date,
                "reason": supersession.reason,
            },
        ))
    for warehouse in dataset.warehouses:
        records.append(CatalogueRecord(
            entity_type="warehouses",
            entity_key=warehouse.code,
            payload={"code": warehouse.code, "name": warehouse.name, "region": warehouse.region},
        ))
    for route in dataset.transfer_routes:
        records.append(CatalogueRecord(
            entity_type="warehouse_transfer_routes",
            entity_key=_entity_key([route.from_code, route.to_code]),
            payload={
                "from_code": route.from_code,
                "to_code": route.to_code,
                "transfer_days": route.transfer_days,
            },
        ))
    return records


def derive_version_id(records: list[CatalogueRecord]) -> UUID:
    """Deterministic ``version_id`` derived from the canonical content digest (UUIDv5)."""
    return UUID(hex=_uuid5_hex(content_sha256(records)))


def _uuid5_hex(name: str) -> str:
    import hashlib

    digest = hashlib.sha1(_VERSION_NAMESPACE.bytes + name.encode("utf-8")).digest()  # noqa: S324
    value = bytearray(digest[:16])
    value[6] = (value[6] & 0x0F) | 0x50  # version 5
    value[8] = (value[8] & 0x3F) | 0x80  # RFC 4122 variant
    return bytes(value).hex()


def build_catalogue(seed: int = DEFAULT_SEED) -> CatalogueSnapshot:
    """Generate the seed-``42`` synthetic catalogue as a typed :class:`CatalogueSnapshot`.

    The ``version_id`` is derived deterministically from the content digest, so the same seed
    always yields the same snapshot (including its id). Labelled ``source="fixture"``.
    """
    dataset = generate_dataset(seed)
    records = dataset_to_records(dataset)
    version_id = derive_version_id(records)
    return build_snapshot(version_id=version_id, source="fixture", records=records)


# --------------------------------------------------------------------------- scenarios

def _compat_set(dataset: CatalogueDataset) -> set[tuple[str, str, str, str]]:
    return {(c.part_number, c.brand, c.model_code, c.config_code) for c in dataset.compatibility}


def _stock_by_part(dataset: CatalogueDataset) -> dict[str, list[StockLevel]]:
    by_part: dict[str, list[StockLevel]] = {}
    for level in dataset.stock:
        by_part.setdefault(level.part_number, []).append(level)
    return by_part


def _has_local_shortage(levels: list[StockLevel]) -> bool:
    """True when at least one warehouse is short while another has stock (needs a transfer)."""
    short = any(level.quantity_on_hand - level.quantity_reserved <= 0 for level in levels)
    elsewhere = any(level.quantity_on_hand - level.quantity_reserved > 0 for level in levels)
    return short and elsewhere


def build_scenarios(dataset: CatalogueDataset) -> list[DemoScenario]:
    """Select four REAL generated records demonstrating the four demo conditions.

    Raises :class:`ScenarioError` when the catalogue cannot demonstrate a required condition —
    a scenario is never fabricated from records that do not support it (F02). Database ids in
    the returned scenarios are the 1-based load ordinals (see module docstring).
    """
    parts = part_ordinals(dataset)
    configs = configuration_ordinals(dataset)
    compat = _compat_set(dataset)
    stock = _stock_by_part(dataset)

    compat_sorted = sorted(
        dataset.compatibility, key=lambda c: (c.brand, c.model_code, c.config_code, c.part_number)
    )
    if not compat_sorted:
        raise ScenarioError("catalogue has no compatibility rows to build scenarios from")
    models_by_key = {(m.brand, m.model_code): m for m in dataset.models}

    # 1. mixed_photo — a real compatible (config, part) with a rendered nameplate attachment.
    first = compat_sorted[0]
    photo_key = (first.brand, first.model_code, first.config_code)
    photo_part = first.part_number
    model = models_by_key[(first.brand, first.model_code)]
    config = next(c for c in model.configurations if c.config_code == first.config_code)
    serial = str(config.serial_start)
    attachment = (
        f"fixtures/nameplates/{first.brand}_{first.model_code}_{serial}.png".replace(" ", "_")
    )
    mixed_photo = DemoScenario(
        id="mixed_photo",
        text=f"محتاج هذا الجزء {photo_part} for my {first.brand} {first.model_code} — see photo / شوف الصورة",
        attachment_path=attachment,
        expected_status="awaiting_review",
        expected_configuration_id=configs[photo_key],
        expected_part_ids=[parts[photo_part]],
    )

    # 2. missing_serial — a model with >= 2 configurations is ambiguous without a serial.
    ambiguous = next(
        (m for m in sorted(dataset.models, key=lambda m: (m.brand, m.model_code))
         if len(m.configurations) >= 2),
        None,
    )
    if ambiguous is None:
        raise ScenarioError("no multi-configuration model exists to demonstrate missing_serial")
    missing_serial = DemoScenario(
        id="missing_serial",
        text=f"I need a hydraulic filter for a {ambiguous.brand} {ambiguous.model_code}.",
        attachment_path=None,
        expected_status="needs_information",
        expected_configuration_id=None,
        expected_part_ids=[],
    )

    # 3. incompatible_number — a real active part that does NOT fit the identified machine.
    incompatible_part = next(
        (
            p.part_number
            for p in sorted(dataset.parts, key=lambda p: p.part_number)
            if p.is_active
            and p.part_number != photo_part
            and (p.part_number, *photo_key) not in compat
        ),
        None,
    )
    if incompatible_part is None:
        raise ScenarioError("no incompatible active part exists to demonstrate incompatible_number")
    incompatible_number = DemoScenario(
        id="incompatible_number",
        text=f"Does part {incompatible_part} fit my {first.brand} {first.model_code} ({first.config_code})?",
        attachment_path=None,
        expected_status="needs_information",
        expected_configuration_id=configs[photo_key],
        expected_part_ids=[],
    )

    # 4. local_shortage — a compatible part short locally but available elsewhere.
    shortage = next(
        (
            c
            for c in compat_sorted
            if c.part_number in stock and _has_local_shortage(stock[c.part_number])
        ),
        None,
    )
    if shortage is None:
        raise ScenarioError("no compatible part has a demonstrable local shortage")
    shortage_key = (shortage.brand, shortage.model_code, shortage.config_code)
    local_shortage = DemoScenario(
        id="local_shortage",
        text=f"Need {shortage.part_number} for {shortage.brand} {shortage.model_code} delivered to Jeddah urgently.",
        attachment_path=None,
        expected_status="awaiting_review",
        expected_configuration_id=configs[shortage_key],
        expected_part_ids=[parts[shortage.part_number]],
    )

    return [mixed_photo, missing_serial, incompatible_number, local_shortage]


def validate_scenarios(dataset: CatalogueDataset, cases: list[DemoScenario]) -> list[str]:
    """Return a list of problems (empty == valid).

    Rejects (F02) any scenario the data cannot back: an expected part that is NOT compatible
    with its claimed configuration, and a ``local_shortage`` whose stock claim is unsupported by
    the generated warehouse quantities. A caller that wants a hard stop should raise on a
    non-empty result.
    """
    errors: list[str] = []

    parts = part_ordinals(dataset)
    configs = configuration_ordinals(dataset)
    part_by_ordinal = {ordinal: number for number, ordinal in parts.items()}
    config_by_ordinal = {ordinal: key for key, ordinal in configs.items()}
    compat = _compat_set(dataset)
    stock = _stock_by_part(dataset)

    seen_ids: set[str] = set()
    for scenario in cases:
        seen_ids.add(scenario.id)
        # Any claimed expected part must be compatible with the claimed configuration.
        if scenario.expected_part_ids:
            if scenario.expected_configuration_id is None:
                errors.append(f"{scenario.id}: expected parts without a configuration")
                continue
            config_key = config_by_ordinal.get(scenario.expected_configuration_id)
            if config_key is None:
                errors.append(
                    f"{scenario.id}: unknown configuration ordinal {scenario.expected_configuration_id}"
                )
                continue
            for part_ordinal in scenario.expected_part_ids:
                number = part_by_ordinal.get(part_ordinal)
                if number is None:
                    errors.append(f"{scenario.id}: unknown part ordinal {part_ordinal}")
                elif (number, *config_key) not in compat:
                    errors.append(
                        f"{scenario.id}: expected part {number} is not compatible with {config_key}"
                    )

        if scenario.id == "mixed_photo" and not scenario.attachment_path:
            errors.append("mixed_photo: missing nameplate attachment")
        if scenario.id == "missing_serial" and scenario.expected_configuration_id is not None:
            errors.append("missing_serial: must stay unresolved (no configuration)")
        if scenario.id == "local_shortage":
            for part_ordinal in scenario.expected_part_ids:
                number = part_by_ordinal.get(part_ordinal)
                if number is None or not _has_local_shortage(stock.get(number, [])):
                    errors.append(
                        f"local_shortage: stock claim for {number} not supported by fixture quantities"
                    )

    missing = _SCENARIO_IDS - seen_ids
    if missing:
        errors.append(f"missing scenarios: {sorted(missing)}")
    return errors


def build_validated_scenarios(dataset: CatalogueDataset) -> list[DemoScenario]:
    """Build the four scenarios and REFUSE (raise) if any cannot be demonstrated."""
    scenarios = build_scenarios(dataset)
    errors = validate_scenarios(dataset, scenarios)
    if errors:
        raise ScenarioError(
            "refusing to emit undemonstrable demo scenarios: " + "; ".join(errors)
        )
    return scenarios


# --------------------------------------------------------------------------- serialization

def _catalogue_document(snapshot: CatalogueSnapshot) -> dict[str, object]:
    """The committed ``catalogue.json`` layout (``{"versions": {...}}``, synthetic marker)."""
    return {
        "synthetic": True,
        "provenance": "PartsIQ synthetic catalogue; seed 42; no real client inventory.",
        "seed": DEFAULT_SEED,
        "version_id": str(snapshot.version_id),
        "source": snapshot.source,
        "content_sha256": snapshot.content_sha256,
        "versions": {
            str(snapshot.version_id): [
                {
                    "entity_type": record.entity_type,
                    "entity_key": record.entity_key,
                    "payload": record.payload,
                }
                for record in snapshot.records
            ]
        },
    }


def _scenarios_document(scenarios: list[DemoScenario], version_id: UUID) -> dict[str, object]:
    """The committed ``scenarios.json`` layout (synthetic marker + the four cases)."""
    return {
        "synthetic": True,
        "provenance": "Derived from the seed-42 synthetic catalogue; not real TAMGO inventory.",
        "seed": DEFAULT_SEED,
        "version_id": str(version_id),
        "scenarios": [scenario.model_dump(mode="json") for scenario in scenarios],
    }


def _dumps(document: dict[str, object]) -> str:
    """Deterministic, human-readable JSON (stable key order, trailing newline)."""
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def render_catalogue_json(snapshot: CatalogueSnapshot) -> str:
    return _dumps(_catalogue_document(snapshot))


def render_scenarios_json(scenarios: list[DemoScenario], version_id: UUID) -> str:
    return _dumps(_scenarios_document(scenarios, version_id))


def write_fixtures(seed: int = DEFAULT_SEED, *, directory: Path | None = None) -> dict[str, Path]:
    """Generate and write ``catalogue.json`` + ``scenarios.json`` deterministically.

    Refuses to write anything if the scenarios cannot be demonstrated by the catalogue.
    Returns the written paths. Byte-identical for a fixed seed.
    """
    target = directory or FIXTURES_DIR
    dataset = generate_dataset(seed)
    records = dataset_to_records(dataset)
    version_id = derive_version_id(records)
    snapshot = build_snapshot(version_id=version_id, source="fixture", records=records)
    scenarios = build_validated_scenarios(dataset)

    target.mkdir(parents=True, exist_ok=True)
    catalogue_path = target / "catalogue.json"
    scenarios_path = target / "scenarios.json"
    catalogue_path.write_text(render_catalogue_json(snapshot), encoding="utf-8")
    scenarios_path.write_text(render_scenarios_json(scenarios, version_id), encoding="utf-8")
    return {"catalogue": catalogue_path, "scenarios": scenarios_path}


if __name__ == "__main__":  # pragma: no cover - manual regeneration entry point
    written = write_fixtures()
    for name, path in written.items():
        print(f"wrote {name}: {path}")
