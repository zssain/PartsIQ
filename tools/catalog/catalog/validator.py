"""Consistency checks that mirror, and go beyond, the database constraints.

Running these before loading gives readable error messages instead of constraint violations, and
catches logical problems the schema cannot express (for example, an active part with no machine).
"""

import re
from collections import Counter, defaultdict
from datetime import date

from catalog.dataset import CatalogDataset

_ARABIC = re.compile("[\u0600-\u06ff]")
_LATIN = re.compile("[A-Za-z]")


def validate_catalog(dataset: CatalogDataset) -> list[str]:
    """Return a list of human-readable problems. An empty list means the dataset is consistent."""
    errors: list[str] = []
    errors.extend(_check_families_and_models(dataset))
    errors.extend(_check_parts_and_aliases(dataset))
    errors.extend(_check_compatibility(dataset))
    errors.extend(_check_supersessions(dataset))
    errors.extend(_check_inventory(dataset))
    return errors


def _duplicates(values: list[object]) -> list[object]:
    return [value for value, count in Counter(values).items() if count > 1]


def _check_families_and_models(dataset: CatalogDataset) -> list[str]:
    errors: list[str] = []
    family_codes = {family.code for family in dataset.families}
    errors += [f"Duplicate family code {code}" for code in _duplicates([f.code for f in dataset.families])]
    errors += [f"Duplicate model {key}" for key in _duplicates([(m.brand, m.model_code) for m in dataset.models])]

    for family in dataset.families:
        if not _ARABIC.search(family.name_ar):
            errors.append(f"Family {family.code} has no Arabic name")
        if not any(model.family_code == family.code for model in dataset.models):
            errors.append(f"Family {family.code} has no models")

    serial_ranges: list[tuple[int, int, str]] = []
    for model in dataset.models:
        if model.family_code not in family_codes:
            errors.append(f"Model {model.model_code} references unknown family {model.family_code}")
        if not model.configurations:
            errors.append(f"Model {model.model_code} has no configurations")
        errors += [f"Model {model.model_code} has duplicate configuration {code}"
                   for code in _duplicates([c.config_code for c in model.configurations])]
        for config in model.configurations:
            label = f"{model.model_code}/{config.config_code}"
            if config.serial_start < 0 or config.serial_start > config.serial_end:
                errors.append(f"Configuration {label} has an invalid serial range")
            serial_ranges.append((config.serial_start, config.serial_end, label))

    serial_ranges.sort()
    for (_, previous_end, previous_label), (start, _, label) in zip(serial_ranges, serial_ranges[1:]):
        if start <= previous_end:
            errors.append(f"Serial ranges overlap: {previous_label} and {label}")
    return errors


def _check_parts_and_aliases(dataset: CatalogDataset) -> list[str]:
    errors: list[str] = []
    part_numbers = [part.part_number for part in dataset.parts]
    errors += [f"Duplicate part number {number}" for number in _duplicates(part_numbers)]
    known = set(part_numbers)
    for part in dataset.parts:
        if not _ARABIC.search(part.name_ar):
            errors.append(f"Part {part.part_number} has no Arabic name")
        if not part.name_en.strip() or not part.category.strip():
            errors.append(f"Part {part.part_number} is missing a name or category")
    errors += [f"Part {number} has duplicate alias {alias!r}"
               for number, alias in _duplicates([(a.part_number, a.alias) for a in dataset.aliases])]
    for alias in dataset.aliases:
        if alias.part_number not in known:
            errors.append(f"Alias {alias.alias!r} references unknown part {alias.part_number}")
        if alias.language == "ar" and not _ARABIC.search(alias.alias):
            errors.append(f"Arabic alias {alias.alias!r} contains no Arabic script")
        if alias.language == "en" and not _LATIN.search(alias.alias):
            errors.append(f"English alias {alias.alias!r} contains no Latin script")
        if alias.language not in {"en", "ar"}:
            errors.append(f"Alias {alias.alias!r} has unsupported language {alias.language}")
    return errors


def _check_compatibility(dataset: CatalogDataset) -> list[str]:
    errors: list[str] = []
    parts = {part.part_number: part for part in dataset.parts}
    configurations = {(m.brand, m.model_code, c.config_code) for m in dataset.models for c in m.configurations}
    errors += [f"Duplicate compatibility row {key}"
               for key in _duplicates([(c.part_number, c.brand, c.model_code, c.config_code) for c in dataset.compatibility])]

    covered_parts: set[str] = set()
    covered_configurations: set[tuple[str, str, str]] = set()
    for row in dataset.compatibility:
        config_key = (row.brand, row.model_code, row.config_code)
        part = parts.get(row.part_number)
        if part is None:
            errors.append(f"Compatibility references unknown part {row.part_number}")
        elif not part.is_active:
            errors.append(f"Compatibility references inactive part {row.part_number}")
        if config_key not in configurations:
            errors.append(f"Compatibility references unknown configuration {config_key}")
        if row.quantity_per_unit <= 0:
            errors.append(f"Compatibility {row.part_number} -> {config_key} has non-positive quantity")
        if not row.source_reference.strip():
            errors.append(f"Compatibility {row.part_number} -> {config_key} has no source reference")
        covered_parts.add(row.part_number)
        covered_configurations.add(config_key)

    errors += [f"Active part {number} fits no machine"
               for number, part in parts.items() if part.is_active and number not in covered_parts]
    errors += [f"Configuration {key} has no compatible parts" for key in sorted(configurations - covered_configurations)]
    return errors


def _check_supersessions(dataset: CatalogDataset) -> list[str]:
    errors: list[str] = []
    parts = {part.part_number: part for part in dataset.parts}
    successor: dict[str, str] = {}
    for row in dataset.supersessions:
        if row.old_part_number in successor:
            errors.append(f"Part {row.old_part_number} has more than one successor")
        successor[row.old_part_number] = row.new_part_number
        if row.old_part_number == row.new_part_number:
            errors.append(f"Part {row.old_part_number} supersedes itself")
        for number in (row.old_part_number, row.new_part_number):
            if number not in parts:
                errors.append(f"Supersession references unknown part {number}")
        old = parts.get(row.old_part_number)
        if old is not None and old.is_active:
            errors.append(f"Superseded part {row.old_part_number} is still active")
        try:
            date.fromisoformat(row.effective_date)
        except ValueError:
            errors.append(f"Supersession {row.old_part_number} has invalid date {row.effective_date!r}")

    for start in successor:
        seen = {start}
        current = start
        while current in successor:
            current = successor[current]
            if current in seen:
                errors.append(f"Supersession cycle detected starting at {start}")
                break
            seen.add(current)
        else:
            final = parts.get(current)
            if final is not None and not final.is_active:
                errors.append(f"Supersession chain from {start} ends at inactive part {current}")

    inactive_without_successor = [n for n, p in parts.items() if not p.is_active and n not in successor]
    errors += [f"Inactive part {number} has no successor" for number in inactive_without_successor]
    return errors


def _check_inventory(dataset: CatalogDataset) -> list[str]:
    errors: list[str] = []
    parts = {part.part_number: part for part in dataset.parts}
    warehouse_codes = [w.code for w in dataset.warehouses]
    errors += [f"Duplicate warehouse {code}" for code in _duplicates(warehouse_codes)]
    errors += [f"Duplicate stock row {key}"
               for key in _duplicates([(s.part_number, s.warehouse_code) for s in dataset.stock])]

    for row in dataset.stock:
        part = parts.get(row.part_number)
        if part is None:
            errors.append(f"Stock references unknown part {row.part_number}")
        elif not part.is_active:
            errors.append(f"Stock recorded for inactive part {row.part_number}")
        if row.warehouse_code not in warehouse_codes:
            errors.append(f"Stock references unknown warehouse {row.warehouse_code}")
        if row.quantity_on_hand < 0 or row.quantity_reserved < 0 or row.quantity_reserved > row.quantity_on_hand:
            errors.append(f"Stock {row.part_number}@{row.warehouse_code} has invalid quantities")

    routes: dict[str, set[str]] = defaultdict(set)
    for route in dataset.transfer_routes:
        if route.from_code == route.to_code:
            errors.append(f"Transfer route {route.from_code} -> {route.to_code} is circular")
        if route.transfer_days < 1:
            errors.append(f"Transfer route {route.from_code} -> {route.to_code} has invalid lead time")
        routes[route.from_code].add(route.to_code)
    for origin in warehouse_codes:
        missing = set(warehouse_codes) - {origin} - routes.get(origin, set())
        errors += [f"Missing transfer route {origin} -> {destination}" for destination in sorted(missing)]
    return errors
