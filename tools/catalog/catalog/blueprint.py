"""Domain blueprint for the synthetic catalogue.

All brands, models, platforms and part numbers are fictional. The structure mirrors real
equipment-dealer catalogues: parts may be shared across a size frame, specific to one model, or
specific to an engine or mast platform, which produces the look-alike distractors that make
parts identification difficult in practice.
"""

from dataclasses import dataclass, field
from typing import Literal

Variance = Literal["platform", "model", "frame"]
PowerSource = Literal["diesel", "electric"]
QuantityRule = Literal["fixed", "cylinders", "by_frame"]
SpecKind = Literal["spin_on_filter", "element", "belt", "hose", "electrical", "kit", "mechanical", "tyre"]


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
    return PartType("OF", "Oil filter", "فلتر زيت", "filters", variance, "spin_on_filter",
                    ("lube filter", "engine oil filter"), ("فلتر الزيت", "فلتر زيت المكينة"), power=power)


def _fuel_filter(variance: Variance) -> PartType:
    return PartType("FF", "Fuel filter", "فلتر وقود", "filters", variance, "spin_on_filter",
                    ("diesel filter",), ("فلتر ديزل", "فلتر الديزل", "فلتر الوقود"), power="diesel")


def _water_separator(variance: Variance) -> PartType:
    return PartType("WS", "Fuel water separator", "فاصل الماء عن الوقود", "filters", variance, "element",
                    ("water separator", "sedimenter", "primary fuel filter"), ("فاصل الماء", "فلتر الماء"),
                    power="diesel")


def _air_filter(variance: Variance, power: PowerSource | None = None) -> PartType:
    return PartType("AF", "Air filter element", "فلتر هواء", "filters", variance, "element",
                    ("air cleaner", "air element"), ("فلتر الهواء", "فلتر هوا"), power=power)


def _belt(variance: Variance, power: PowerSource | None = None) -> PartType:
    return PartType("FB", "Fan belt", "سير المروحة", "belts", variance, "belt",
                    ("v belt", "drive belt"), ("سير", "سير المروحه", "سير الدينامو"), power=power)


def _hydraulic_filter(variance: Variance) -> PartType:
    return PartType("HF", "Hydraulic filter", "فلتر هيدروليك", "filters", variance, "element",
                    ("hydraulic return filter", "hydraulic oil filter"), ("فلتر الهيدروليك",))


GENERATORS = FamilySpec(
    code="GENSET",
    name_en="Diesel generators",
    name_ar="مولدات كهربائية",
    brand="Veltrano Power",
    prefix="VP",
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
        PartType("AV", "Automatic voltage regulator", "منظم الجهد الآلي", "electrical", "frame", "electrical",
                 ("avr", "voltage regulator"), ("منظم جهد", "منظم الفولت")),
        PartType("GK", "Top end gasket kit", "طقم جوانات", "engine", "platform", "kit",
                 ("head gasket kit", "gasket set"), ("جوانات راس", "طقم جوان")),
        PartType("FI", "Fuel injector", "بخاخ وقود", "engine", "platform", "mechanical",
                 ("injector", "injector nozzle"), ("بخاخ", "بخاخات", "بخاخ ديزل"), quantity_rule="cylinders"),
    ),
)

COMPRESSORS = FamilySpec(
    code="COMPRESSOR",
    name_en="Air compressors",
    name_ar="ضواغط هواء",
    brand="Corvane Air",
    prefix="CA",
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
        PartType("OF", "Compressor oil filter", "فلتر زيت الكمبروسر", "filters", "frame", "spin_on_filter",
                 ("oil filter", "lube filter"), ("فلتر زيت", "فلتر الزيت")),
        _air_filter("frame"),
        _fuel_filter("platform"),
        PartType("SE", "Air oil separator element", "فاصل الزيت والهواء", "filters", "model", "element",
                 ("separator", "oil separator", "separator element"), ("فاصل زيت", "سبريتر", "فلتر السبريتر")),
        PartType("IV", "Intake valve kit", "طقم صمام السحب", "valves", "frame", "kit",
                 ("inlet valve kit", "unloader kit"), ("صمام سحب", "طقم بلف السحب")),
        PartType("MV", "Minimum pressure valve kit", "طقم صمام الضغط الأدنى", "valves", "frame", "kit",
                 ("mpv kit", "minimum pressure valve"), ("بلف الضغط", "صمام الضغط")),
        _belt("model"),
        PartType("TS", "Discharge temperature sensor", "حساس حرارة", "electrical", "model", "electrical",
                 ("temp sensor", "temperature probe"), ("حساس الحرارة", "سنسر حرارة")),
    ),
)

FORKLIFTS = FamilySpec(
    code="FORKLIFT",
    name_en="Forklift trucks",
    name_ar="رافعات شوكية",
    brand="Halvorn Lift",
    prefix="HL",
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
                 ("lift chain", "mast chain"), ("جنزير", "جنزير الرافعة", "جنزير الكلارك"), quantity=2),
        PartType("BP", "Brake shoe set", "طقم فحمات فرامل", "brakes", "frame", "kit",
                 ("brake pads", "brake shoes"), ("فحمات", "فحمات فرامل", "فحمات الكلارك")),
        PartType("TY", "Drive tyre", "إطار القيادة", "wheels", "model", "tyre",
                 ("front tyre", "front tire", "solid tyre"), ("كفر", "تاير", "كفر امامي"), quantity=2),
        PartType("BT", "Traction battery", "بطارية الجر", "electrical", "model", "electrical",
                 ("forklift battery", "traction battery pack"), ("بطارية", "بطارية الكلارك"), power="electric"),
    ),
)

EXCAVATORS = FamilySpec(
    code="EXCAVATOR",
    name_en="Crawler excavators",
    name_ar="حفارات",
    brand="Duneforge",
    prefix="DF",
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
        PartType("TA", "Track adjuster seal kit", "طقم جلود شداد الجنزير", "undercarriage", "frame", "kit",
                 ("track tensioner seal kit", "recoil seal kit"), ("جلود الشداد", "طقم شداد الجنزير")),
    ),
)

FAMILIES: tuple[FamilySpec, ...] = (GENERATORS, COMPRESSORS, FORKLIFTS, EXCAVATORS)

WAREHOUSES: tuple[tuple[str, str, str], ...] = (
    ("JED", "Western Regional Warehouse (Jeddah)", "Western"),
    ("RUH", "Central Regional Warehouse (Riyadh)", "Central"),
    ("DMM", "Eastern Regional Warehouse (Dammam)", "Eastern"),
)

# Synthetic planning lead times in days; symmetric.
TRANSFER_DAYS: dict[frozenset[str], int] = {
    frozenset({"JED", "RUH"}): 2,
    frozenset({"RUH", "DMM"}): 1,
    frozenset({"JED", "DMM"}): 3,
}
