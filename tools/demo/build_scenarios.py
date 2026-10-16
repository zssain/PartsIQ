"""Derive the four deterministic demo scenarios from the seed-42 catalogue.

Entry contracts (FLOW.md row 05):
    def build_scenarios(dataset: CatalogDataset) -> list[DemoScenario]
    def render_nameplate(model: str, serial: str, destination: Path) -> None
    def validate_scenarios(scenarios, dataset) -> list[str]

Principles (F02):
  * Scenario identifiers are SELECTED from real generated records, never hardcoded.
  * Base loading inserts records in dataset order, so a record's database SERIAL id is
    its 1-based ordinal in the dataset. The scenarios carry those ordinals; the same
    controlled seed transaction assigns the same ids on load.
  * Generation FAILS (build_scenarios raises) when an expected outcome cannot be
    demonstrated by the fixtures.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
# The legacy catalogue package runs with tools/catalog on the path (its pytest.ini).
sys.path.insert(0, str(REPO_ROOT / "tools" / "catalog"))
sys.path.insert(0, str(REPO_ROOT / "libs" / "partsiq_common"))

from catalog.dataset import CatalogDataset  # noqa: E402
from catalog.validator import validate_catalog  # noqa: E402

from partsiq_common.contracts import DemoScenario  # noqa: E402

NAMEPLATE_DIR = REPO_ROOT / "tools" / "demo" / "nameplates"


# --------------------------------------------------------------------------- ordinals
def part_ordinals(dataset: CatalogDataset) -> dict[str, int]:
    """part_number -> 1-based insertion ordinal (== loaded SERIAL id)."""
    return {part.part_number: index + 1 for index, part in enumerate(dataset.parts)}


def configuration_ordinals(dataset: CatalogDataset) -> dict[tuple[str, str, str], int]:
    """(brand, model_code, config_code) -> 1-based ordinal across models in load order."""
    ordinals: dict[tuple[str, str, str], int] = {}
    index = 0
    for model in dataset.models:
        for config in model.configurations:
            index += 1
            ordinals[(model.brand, model.model_code, config.config_code)] = index
    return ordinals


def _compat_set(dataset: CatalogDataset) -> set[tuple[str, str, str, str]]:
    return {(c.part_number, c.brand, c.model_code, c.config_code) for c in dataset.compatibility}


def _stock_by_part(dataset: CatalogDataset) -> dict[str, list]:
    by_part: dict[str, list] = {}
    for level in dataset.stock:
        by_part.setdefault(level.part_number, []).append(level)
    return by_part


def _has_local_shortage(levels: list) -> bool:
    """True when at least one warehouse is short while another has stock (needs transfer)."""
    short = any(level.quantity_on_hand - level.quantity_reserved <= 0 for level in levels)
    elsewhere = any(level.quantity_on_hand - level.quantity_reserved > 0 for level in levels)
    return short and elsewhere


# --------------------------------------------------------------------------- build
def build_scenarios(dataset: CatalogDataset) -> list[DemoScenario]:
    """Select four real records demonstrating the four demo conditions."""
    parts = part_ordinals(dataset)
    configs = configuration_ordinals(dataset)
    compat = _compat_set(dataset)
    stock = _stock_by_part(dataset)

    # Deterministic iteration order.
    compat_sorted = sorted(
        dataset.compatibility, key=lambda c: (c.brand, c.model_code, c.config_code, c.part_number)
    )
    models_by_key = {(m.brand, m.model_code): m for m in dataset.models}

    # 1. mixed_photo: a real compatible (config, part) with a rendered nameplate.
    first = compat_sorted[0]
    photo_key = (first.brand, first.model_code, first.config_code)
    photo_part = first.part_number
    model = models_by_key[(first.brand, first.model_code)]
    config = next(c for c in model.configurations if c.config_code == first.config_code)
    serial = str(config.serial_start)
    attachment = f"tools/demo/nameplates/{first.brand}_{first.model_code}_{serial}.png".replace(" ", "_")
    mixed_photo = DemoScenario(
        id="mixed_photo",
        text=f"محتاج هذا الجزء {photo_part} for my {first.brand} {first.model_code} — see photo / شوف الصورة",
        attachment_path=attachment,
        expected_status="awaiting_review",
        expected_configuration_id=configs[photo_key],
        expected_part_ids=[parts[photo_part]],
    )

    # 2. missing_serial: a model with >= 2 configurations is ambiguous without a serial.
    ambiguous = next(
        (m for m in sorted(dataset.models, key=lambda m: (m.brand, m.model_code)) if len(m.configurations) >= 2),
        None,
    )
    if ambiguous is None:
        raise ValueError("no multi-configuration model exists to demonstrate missing_serial")
    missing_serial = DemoScenario(
        id="missing_serial",
        text=f"I need a hydraulic filter for a {ambiguous.brand} {ambiguous.model_code}.",
        attachment_path=None,
        expected_status="needs_information",
        expected_configuration_id=None,
        expected_part_ids=[],
    )

    # 3. incompatible_number: a real active part that does NOT fit the identified machine.
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
        raise ValueError("no incompatible active part exists to demonstrate incompatible_number")
    incompatible_number = DemoScenario(
        id="incompatible_number",
        text=f"Does part {incompatible_part} fit my {first.brand} {first.model_code} ({first.config_code})?",
        attachment_path=None,
        expected_status="needs_information",
        expected_configuration_id=configs[photo_key],
        expected_part_ids=[],
    )

    # 4. local_shortage: a compatible part short locally but available elsewhere.
    shortage = next(
        (
            c
            for c in compat_sorted
            if c.part_number in stock and _has_local_shortage(stock[c.part_number])
        ),
        None,
    )
    if shortage is None:
        raise ValueError("no compatible part has a demonstrable local shortage")
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


# --------------------------------------------------------------------------- validate
def validate_scenarios(scenarios: list[DemoScenario], dataset: CatalogDataset) -> list[str]:
    """Return errors (empty == valid). Rejects uncompatible expected parts and
    unsupported stock claims, so a demo can never assert something the data denies."""
    errors: list[str] = list(validate_catalog(dataset))

    parts = part_ordinals(dataset)
    configs = configuration_ordinals(dataset)
    part_by_ordinal = {ordinal: number for number, ordinal in parts.items()}
    config_by_ordinal = {ordinal: key for key, ordinal in configs.items()}
    compat = _compat_set(dataset)
    stock = _stock_by_part(dataset)

    seen_ids = set()
    for scenario in scenarios:
        seen_ids.add(scenario.id)
        # Any claimed expected part must be compatible with the claimed configuration.
        if scenario.expected_part_ids:
            if scenario.expected_configuration_id is None:
                errors.append(f"{scenario.id}: expected parts without a configuration")
                continue
            config_key = config_by_ordinal.get(scenario.expected_configuration_id)
            if config_key is None:
                errors.append(f"{scenario.id}: unknown configuration ordinal {scenario.expected_configuration_id}")
                continue
            for part_ordinal in scenario.expected_part_ids:
                number = part_by_ordinal.get(part_ordinal)
                if number is None:
                    errors.append(f"{scenario.id}: unknown part ordinal {part_ordinal}")
                elif (number, *config_key) not in compat:
                    errors.append(f"{scenario.id}: expected part {number} is not compatible with {config_key}")

        if scenario.id == "mixed_photo" and not scenario.attachment_path:
            errors.append("mixed_photo: missing nameplate attachment")
        if scenario.id == "missing_serial" and scenario.expected_configuration_id is not None:
            errors.append("missing_serial: must stay unresolved (no configuration)")
        if scenario.id == "local_shortage":
            for part_ordinal in scenario.expected_part_ids:
                number = part_by_ordinal.get(part_ordinal)
                if number is None or not _has_local_shortage(stock.get(number, [])):
                    errors.append(f"local_shortage: stock claim for {number} not supported by fixture quantities")

    expected_ids = {"mixed_photo", "missing_serial", "incompatible_number", "local_shortage"}
    missing = expected_ids - seen_ids
    if missing:
        errors.append(f"missing scenarios: {sorted(missing)}")
    return errors


# --------------------------------------------------------------------------- rendering
def render_nameplate(model: str, serial: str, destination: Path) -> None:
    """Render a synthetic machine nameplate PNG (model + serial). Deterministic."""
    from PIL import Image, ImageDraw

    destination.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (480, 240), color=(28, 40, 66))  # brand navy
    draw = ImageDraw.Draw(image)
    draw.rectangle([(10, 10), (470, 230)], outline=(201, 162, 39), width=3)  # brand gold
    draw.text((28, 40), "PartsIQ synthetic nameplate", fill=(230, 230, 230))
    draw.text((28, 100), f"MODEL: {model}", fill=(255, 255, 255))
    draw.text((28, 140), f"SERIAL: {serial}", fill=(255, 255, 255))
    image.save(destination, format="PNG")
