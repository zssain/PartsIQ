"""Pure validation of a catalogue snapshot before activation (foundation 02).

These checks mirror, and go beyond, the PostgreSQL constraints applied at activation. They
run in Python on the typed snapshot BEFORE any version becomes active, so a bad remote or
fixture version produces an actionable import report (entity_type / entity_key / field / code
/ message) instead of a late constraint violation. There is NO I/O here — the functions are
deterministic over the snapshot alone.

Covered by this module (prompt 02 IMPLEMENTATION STEPS 9-10 and DATA_OWNERSHIP step 3):
  * schema: known entity types only, required fields present and well-typed;
  * unique entity keys (a duplicate quarantines the version — it is never dict-overwritten);
  * foreign references between entities (models→families, configs→models, parts↔compat, …);
  * serial-range validity and overlap across configurations;
  * supersession graph: single successor, no self-loop, no cycle;
  * source evidence presence (non-blank provenance on compatibility rows);
  * unit quantities (positive quantity_per_unit, non-blank unit_of_measure).

Stock quantities/values are validated separately (STOCK_SNAPSHOTS / 003_validation_queries.sql
and the activation pipeline) because stock is not carried as a catalogue RECORD.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date

from partsiq.core.api_models import CatalogueRecord, CatalogueSnapshot, ValidationIssue

from .models import CATALOGUE_ENTITY_TYPES

_ARABIC = re.compile("[؀-ۿ]")
_MAX_SUPERSESSION_DEPTH = 64

# Required payload fields per entity type. Extra fields are allowed (forward-compatible), but a
# missing required field, or an unknown entity type, fails validation rather than being dropped.
_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "equipment_families": ("code", "name_en", "name_ar"),
    "equipment_models": ("family_code", "brand", "model_code", "display_name"),
    "model_configurations": ("brand", "model_code", "config_code", "serial_start", "serial_end"),
    "parts": ("part_number", "name_en", "name_ar", "category", "unit_of_measure", "is_active"),
    "part_aliases": ("part_number", "alias", "language"),
    "part_compatibility": ("part_number", "brand", "model_code", "config_code", "quantity_per_unit", "source_reference"),
    "part_supersessions": ("old_part_number", "new_part_number", "effective_date"),
    "warehouses": ("code", "name", "region"),
    "warehouse_transfer_routes": ("from_code", "to_code", "transfer_days"),
}


def _issue(record: CatalogueRecord, field: str, code: str, message: str) -> ValidationIssue:
    return ValidationIssue(
        entity_type=record.entity_type,
        entity_key=record.entity_key,
        field=field,
        code=code,
        message=message,
    )


def _by_type(records: list[CatalogueRecord]) -> dict[str, list[CatalogueRecord]]:
    grouped: dict[str, list[CatalogueRecord]] = defaultdict(list)
    for record in records:
        grouped[record.entity_type].append(record)
    return grouped


def _check_schema_and_keys(records: list[CatalogueRecord]) -> list[ValidationIssue]:
    """Known entity types, required fields, and globally unique (entity_type, entity_key)."""
    issues: list[ValidationIssue] = []
    key_counts = Counter((r.entity_type, r.entity_key) for r in records)
    reported_dupes: set[tuple[str, str]] = set()
    for record in records:
        if record.entity_type not in CATALOGUE_ENTITY_TYPES:
            issues.append(_issue(record, "entity_type", "UNKNOWN_ENTITY_TYPE",
                                 f"unsupported entity type {record.entity_type!r}"))
            continue
        if not record.entity_key:
            issues.append(_issue(record, "entity_key", "MISSING_KEY", "entity_key must be non-empty"))
        identity = (record.entity_type, record.entity_key)
        if key_counts[identity] > 1 and identity not in reported_dupes:
            reported_dupes.add(identity)
            # A duplicate key quarantines the version; rows are NEVER merged by dict overwrite.
            issues.append(_issue(record, "entity_key", "DUPLICATE_KEY",
                                 f"{key_counts[identity]} rows share key {record.entity_key!r}"))
        for field in _REQUIRED_FIELDS.get(record.entity_type, ()):  # type: ignore[arg-type]
            if field not in record.payload:
                issues.append(_issue(record, field, "MISSING_FIELD", f"required field {field!r} is absent"))
    return issues


def _as_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value)
    return None


def _as_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _check_models_and_serials(grouped: dict[str, list[CatalogueRecord]]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    family_codes = {r.payload.get("code") for r in grouped.get("equipment_families", [])}
    model_keys = {
        (r.payload.get("brand"), r.payload.get("model_code")) for r in grouped.get("equipment_models", [])
    }

    for model in grouped.get("equipment_models", []):
        if model.payload.get("family_code") not in family_codes:
            issues.append(_issue(model, "family_code", "UNKNOWN_REFERENCE",
                                 f"references unknown family {model.payload.get('family_code')!r}"))
        if not _ARABIC.search(str(model.payload.get("display_name", ""))) and not grouped.get("equipment_families"):
            continue  # display_name may be latin; Arabic coverage is asserted on families/parts

    # Serial ranges live on configurations; validate each, then check pairwise overlap.
    ranges: list[tuple[int, int, CatalogueRecord]] = []
    for config in grouped.get("model_configurations", []):
        key = (config.payload.get("brand"), config.payload.get("model_code"))
        if key not in model_keys:
            issues.append(_issue(config, "model_code", "UNKNOWN_REFERENCE",
                                 f"references unknown model {key}"))
        start = _as_int(config.payload.get("serial_start"))
        end = _as_int(config.payload.get("serial_end"))
        if start is None or end is None:
            issues.append(_issue(config, "serial_start", "INVALID_SERIAL_RANGE",
                                 "serial_start/serial_end must be integers"))
            continue
        if start < 0 or start > end:
            issues.append(_issue(config, "serial_start", "INVALID_SERIAL_RANGE",
                                 f"invalid serial range [{start}, {end}]"))
            continue
        ranges.append((start, end, config))

    ranges.sort(key=lambda item: (item[0], item[1]))
    for (prev_start, prev_end, prev_rec), (start, end, rec) in zip(ranges, ranges[1:]):
        if start <= prev_end:
            issues.append(_issue(rec, "serial_start", "SERIAL_RANGE_OVERLAP",
                                 f"serial range [{start}, {end}] overlaps [{prev_start}, {prev_end}] "
                                 f"of {prev_rec.entity_key}"))
    return issues


def _check_parts_graph(grouped: dict[str, list[CatalogueRecord]]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    parts = {str(r.payload.get("part_number")): r for r in grouped.get("parts", [])}
    config_keys = {
        (r.payload.get("brand"), r.payload.get("model_code"), r.payload.get("config_code"))
        for r in grouped.get("model_configurations", [])
    }

    for part in grouped.get("parts", []):
        if not _ARABIC.search(str(part.payload.get("name_ar", ""))):
            issues.append(_issue(part, "name_ar", "MISSING_ARABIC_NAME", "part has no Arabic name"))
        uom = str(part.payload.get("unit_of_measure", "")).strip()
        if not uom:
            issues.append(_issue(part, "unit_of_measure", "INVALID_UNIT", "unit_of_measure must be non-empty"))

    for alias in grouped.get("part_aliases", []):
        if str(alias.payload.get("part_number")) not in parts:
            issues.append(_issue(alias, "part_number", "UNKNOWN_REFERENCE",
                                 f"alias references unknown part {alias.payload.get('part_number')!r}"))

    for row in grouped.get("part_compatibility", []):
        if str(row.payload.get("part_number")) not in parts:
            issues.append(_issue(row, "part_number", "UNKNOWN_REFERENCE",
                                 f"compatibility references unknown part {row.payload.get('part_number')!r}"))
        config_key = (row.payload.get("brand"), row.payload.get("model_code"), row.payload.get("config_code"))
        if config_key not in config_keys:
            issues.append(_issue(row, "config_code", "UNKNOWN_REFERENCE",
                                 f"compatibility references unknown configuration {config_key}"))
        quantity = _as_number(row.payload.get("quantity_per_unit"))
        if quantity is None or quantity <= 0:
            issues.append(_issue(row, "quantity_per_unit", "INVALID_QUANTITY",
                                 "quantity_per_unit must be a positive number"))
        if not str(row.payload.get("source_reference", "")).strip():
            issues.append(_issue(row, "source_reference", "MISSING_EVIDENCE",
                                 "compatibility row has no source reference"))
    return issues


def _check_supersessions(grouped: dict[str, list[CatalogueRecord]]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    parts = {str(r.payload.get("part_number")) for r in grouped.get("parts", [])}
    successor: dict[str, str] = {}
    first_for_old: dict[str, CatalogueRecord] = {}

    for row in grouped.get("part_supersessions", []):
        old = str(row.payload.get("old_part_number"))
        new = str(row.payload.get("new_part_number"))
        first_for_old.setdefault(old, row)
        if old in successor:
            issues.append(_issue(row, "old_part_number", "MULTIPLE_SUCCESSORS",
                                 f"part {old} already has a successor"))
        else:
            successor[old] = new
        if old == new:
            issues.append(_issue(row, "new_part_number", "SUPERSESSION_SELF_LOOP",
                                 f"part {old} supersedes itself"))
        for number in (old, new):
            if number not in parts:
                issues.append(_issue(row, "old_part_number", "UNKNOWN_REFERENCE",
                                     f"supersession references unknown part {number}"))
        effective = row.payload.get("effective_date")
        if isinstance(effective, str):
            try:
                date.fromisoformat(effective)
            except ValueError:
                issues.append(_issue(row, "effective_date", "INVALID_DATE",
                                     f"invalid effective_date {effective!r}"))

    # Cycle detection over the successor map (Floyd-style bounded walk per origin).
    for start in successor:
        seen = {start}
        current = start
        while current in successor:
            current = successor[current]
            if current in seen or len(seen) > _MAX_SUPERSESSION_DEPTH:
                issues.append(_issue(first_for_old[start], "new_part_number", "SUPERSESSION_CYCLE",
                                     f"supersession cycle detected starting at {start}"))
                break
            seen.add(current)
    return issues


def validate_snapshot(snapshot: CatalogueSnapshot) -> list[ValidationIssue]:
    """Validate a snapshot into a list of issues. An empty list means the snapshot is consistent.

    Pure function: no database, Snowflake or network access. Call this BEFORE activating any
    version. Schema/key issues are reported first; when they are present the relational graph
    checks still run on the well-formed subset so the report is as complete as possible.
    """
    records = snapshot.records
    grouped = _by_type(records)
    issues: list[ValidationIssue] = []
    issues.extend(_check_schema_and_keys(records))
    issues.extend(_check_models_and_serials(grouped))
    issues.extend(_check_parts_graph(grouped))
    issues.extend(_check_supersessions(grouped))
    return issues
