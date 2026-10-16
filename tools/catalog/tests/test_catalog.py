from dataclasses import replace

from catalog.dataset import CatalogDataset, Supersession
from catalog.generator import generate_catalog
from catalog.validator import validate_catalog


def test_generated_catalog_is_valid() -> None:
    assert validate_catalog(generate_catalog(42)) == []


def test_generation_is_deterministic() -> None:
    assert generate_catalog(7) == generate_catalog(7)
    assert generate_catalog(7) != generate_catalog(8)


def test_dataset_round_trips_through_json() -> None:
    dataset = generate_catalog(42)
    assert CatalogDataset.from_json(dataset.to_json()) == dataset


def test_catalog_contains_realistic_difficulty() -> None:
    dataset = generate_catalog(42)
    assert dataset.supersessions, "customers quoting superseded numbers must be represented"
    assert any(s.quantity_on_hand == 0 for s in dataset.stock), "stock-outs must be represented"
    names = [part.name_en for part in dataset.parts if part.is_active]
    assert len(names) > len(set(names)), "look-alike parts with identical names must exist"
    assert all(model.configurations for model in dataset.models)


def test_validator_detects_overlapping_serial_ranges() -> None:
    dataset = generate_catalog(42)
    first, second = dataset.models[0], dataset.models[1]
    overlapping = replace(
        second,
        configurations=(replace(second.configurations[0], serial_start=first.configurations[0].serial_start),)
        + second.configurations[1:],
    )
    corrupted = replace(dataset, models=(first, overlapping) + dataset.models[2:])
    assert any("overlap" in error for error in validate_catalog(corrupted))


def test_validator_detects_supersession_cycle() -> None:
    dataset = generate_catalog(42)
    link = dataset.supersessions[0]
    cycle = Supersession(link.new_part_number, link.old_part_number, link.effective_date, "test")
    corrupted = replace(dataset, supersessions=dataset.supersessions + (cycle,))
    assert any("cycle" in error for error in validate_catalog(corrupted))


def test_validator_detects_dangling_compatibility() -> None:
    dataset = generate_catalog(42)
    dangling = replace(dataset.compatibility[0], part_number="XX-XX-0000")
    corrupted = replace(dataset, compatibility=dataset.compatibility + (dangling,))
    assert any("unknown part XX-XX-0000" in error for error in validate_catalog(corrupted))
