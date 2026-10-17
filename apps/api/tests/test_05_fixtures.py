"""Foundation 05 acceptance: synthetic catalogue + the four demo scenario fixtures.

Every test here is OFFLINE and deterministic. It exercises the real behaviour described in
prompt 05's IMPLEMENTATION STEPS and each rejected boundary (F02):

  * determinism — a fresh generation (seed 42) is byte-identical to the committed files;
  * the four scenarios have the typed :class:`DemoScenario` shape and ids;
  * the valid set is accepted by :func:`validate_scenarios`;
  * an expected part that is NOT compatible with its configuration is REJECTED;
  * a ``local_shortage`` whose stock claim is unsupported is REJECTED;
  * the committed fixture loads through :class:`FixtureCatalogueRepository` into a snapshot that
    passes foundation 02's :func:`validate_snapshot`;
  * nothing is marked real client inventory (the ``synthetic`` marker is present).

No fixture inserts an approved recommendation, and no network/database I/O occurs.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from partsiq.catalogue import fixtures as fx
from partsiq.catalogue.fixture_repository import FixtureCatalogueRepository
from partsiq.catalogue.models import CATALOGUE_ENTITY_TYPES, CatalogueSource, content_sha256
from partsiq.catalogue.validation import validate_snapshot
from partsiq.core.api_models import CatalogueSnapshot, DemoScenario

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES_DIR = _REPO_ROOT / "fixtures"
_CATALOGUE_JSON = _FIXTURES_DIR / "catalogue.json"
_SCENARIOS_JSON = _FIXTURES_DIR / "scenarios.json"
_SCENARIO_IDS = ("mixed_photo", "missing_serial", "incompatible_number", "local_shortage")


# --- the generator is deterministic -------------------------------------

def test_build_catalogue_is_deterministic() -> None:
    first = fx.build_catalogue(42)
    second = fx.build_catalogue(42)
    assert first.version_id == second.version_id
    assert first.content_sha256 == second.content_sha256
    assert first.source == "fixture"
    # the digest is self-consistent with the records
    assert first.content_sha256 == content_sha256(first.records)


def test_committed_files_match_a_fresh_generation(tmp_path: Path) -> None:
    """Regenerating with the same seed yields byte-identical committed fixtures."""
    assert _CATALOGUE_JSON.is_file(), "fixtures/catalogue.json is missing"
    assert _SCENARIOS_JSON.is_file(), "fixtures/scenarios.json is missing"

    fx.write_fixtures(42, directory=tmp_path)
    assert (tmp_path / "catalogue.json").read_bytes() == _CATALOGUE_JSON.read_bytes()
    assert (tmp_path / "scenarios.json").read_bytes() == _SCENARIOS_JSON.read_bytes()


def test_render_helpers_match_committed_text() -> None:
    snapshot = fx.build_catalogue(42)
    dataset = fx.generate_dataset(42)
    scenarios = fx.build_validated_scenarios(dataset)
    assert fx.render_catalogue_json(snapshot) == _CATALOGUE_JSON.read_text(encoding="utf-8")
    assert fx.render_scenarios_json(scenarios, snapshot.version_id) == _SCENARIOS_JSON.read_text(
        encoding="utf-8"
    )


# --- catalogue shape -----------------------------------------------------

def test_catalogue_records_use_only_known_entity_types() -> None:
    snapshot = fx.build_catalogue(42)
    assert len(snapshot.records) > 0
    types = {record.entity_type for record in snapshot.records}
    assert types <= CATALOGUE_ENTITY_TYPES
    # every catalogue entity type except stock-only ones is represented
    assert "parts" in types and "part_compatibility" in types and "equipment_models" in types


def test_parts_and_configs_keyed_by_one_based_load_ordinal() -> None:
    dataset = fx.generate_dataset(42)
    snapshot = fx.build_catalogue(42)
    expected_part_ids = {str(o) for o in fx.part_ordinals(dataset).values()}
    expected_config_ids = {str(o) for o in fx.configuration_ordinals(dataset).values()}
    part_keys = {r.entity_key for r in snapshot.records if r.entity_type == "parts"}
    config_keys = {r.entity_key for r in snapshot.records if r.entity_type == "model_configurations"}
    assert part_keys == expected_part_ids
    assert config_keys == expected_config_ids
    # ordinals are 1-based and contiguous
    assert min(int(k) for k in part_keys) == 1
    assert min(int(k) for k in config_keys) == 1


# --- scenarios -----------------------------------------------------------

def test_four_scenarios_have_expected_ids_and_typed_shape() -> None:
    dataset = fx.generate_dataset(42)
    scenarios = fx.build_scenarios(dataset)
    assert [s.id for s in scenarios] == list(_SCENARIO_IDS)
    for scenario in scenarios:
        assert isinstance(scenario, DemoScenario)  # typed contract shape

    by_id = {s.id: s for s in scenarios}
    assert by_id["mixed_photo"].expected_status == "awaiting_review"
    assert by_id["mixed_photo"].attachment_path  # photo scenario carries an attachment reference
    assert by_id["mixed_photo"].expected_part_ids  # resolves to a compatible part
    assert by_id["missing_serial"].expected_status == "needs_information"
    assert by_id["missing_serial"].expected_configuration_id is None  # stays unresolved
    assert by_id["missing_serial"].expected_part_ids == []
    assert by_id["incompatible_number"].expected_status == "needs_information"
    assert by_id["incompatible_number"].expected_part_ids == []  # refuses to guess a part
    assert by_id["local_shortage"].expected_status == "awaiting_review"
    assert by_id["local_shortage"].expected_part_ids


def test_mixed_language_photo_scenario_is_bilingual() -> None:
    dataset = fx.generate_dataset(42)
    scenario = next(s for s in fx.build_scenarios(dataset) if s.id == "mixed_photo")
    assert fx._ARABIC.search(scenario.text), "mixed_photo text must contain Arabic"
    assert any("a" <= ch.lower() <= "z" for ch in scenario.text), "and Latin"


def test_valid_scenario_set_is_accepted() -> None:
    dataset = fx.generate_dataset(42)
    scenarios = fx.build_scenarios(dataset)
    assert fx.validate_scenarios(dataset, scenarios) == []
    # the refusing wrapper does not raise on the valid set
    assert fx.build_validated_scenarios(dataset) == scenarios


# --- rejected boundaries (F02) ------------------------------------------

def test_incompatible_expected_part_is_rejected() -> None:
    """A scenario claiming a part that is NOT compatible with its config must be refused."""
    dataset = fx.generate_dataset(42)
    good = next(s for s in fx.build_scenarios(dataset) if s.id == "mixed_photo")

    parts = fx.part_ordinals(dataset)
    compat = fx._compat_set(dataset)
    config_key = {o: k for k, o in fx.configuration_ordinals(dataset).items()}[
        good.expected_configuration_id
    ]
    # Find an active part that does NOT fit that configuration.
    bad_part_ordinal = next(
        parts[number]
        for number in sorted(parts)
        if (number, *config_key) not in compat
    )
    tampered = DemoScenario(
        id="incompatible_number",
        text="tampered: claims an incompatible part is compatible",
        attachment_path=None,
        expected_status="awaiting_review",
        expected_configuration_id=good.expected_configuration_id,
        expected_part_ids=[bad_part_ordinal],
    )
    cases = [s for s in fx.build_scenarios(dataset) if s.id != "incompatible_number"] + [tampered]
    errors = fx.validate_scenarios(dataset, cases)
    assert any("not compatible" in e for e in errors), errors


def test_unsupported_local_shortage_stock_claim_is_rejected() -> None:
    """A local_shortage over a part that is NOT short anywhere must be refused."""
    dataset = fx.generate_dataset(42)
    parts = fx.part_ordinals(dataset)
    compat = fx._compat_set(dataset)
    stock = fx._stock_by_part(dataset)
    configs_by_ordinal = {o: k for k, o in fx.configuration_ordinals(dataset).items()}

    # Pick a compatible (part, config) whose part has NO demonstrable local shortage.
    choice = None
    for compat_row in sorted(
        dataset.compatibility, key=lambda c: (c.brand, c.model_code, c.config_code, c.part_number)
    ):
        levels = stock.get(compat_row.part_number, [])
        if not fx._has_local_shortage(levels):
            config_ordinal = {k: o for o, k in configs_by_ordinal.items()}[
                (compat_row.brand, compat_row.model_code, compat_row.config_code)
            ]
            assert (compat_row.part_number, compat_row.brand, compat_row.model_code,
                    compat_row.config_code) in compat  # genuinely compatible, so only stock fails
            choice = (parts[compat_row.part_number], config_ordinal)
            break
    assert choice is not None, "expected at least one compatible part without a local shortage"

    tampered = DemoScenario(
        id="local_shortage",
        text="tampered: claims a local shortage the stock does not support",
        attachment_path=None,
        expected_status="awaiting_review",
        expected_configuration_id=choice[1],
        expected_part_ids=[choice[0]],
    )
    cases = [s for s in fx.build_scenarios(dataset) if s.id != "local_shortage"] + [tampered]
    errors = fx.validate_scenarios(dataset, cases)
    assert any("stock claim" in e for e in errors), errors
    assert all("not compatible" not in e for e in errors), (
        "the part is compatible; only the stock claim should fail"
    )


def test_missing_scenario_is_reported() -> None:
    dataset = fx.generate_dataset(42)
    only_three = [s for s in fx.build_scenarios(dataset) if s.id != "local_shortage"]
    errors = fx.validate_scenarios(dataset, only_three)
    assert any("missing scenarios" in e and "local_shortage" in e for e in errors), errors


def test_build_validated_scenarios_raises_on_undemonstrable_set() -> None:
    dataset = fx.generate_dataset(42)
    # A catalogue with no compatibility cannot demonstrate any scenario.
    empty = fx.CatalogueDataset(
        seed=42, families=dataset.families, models=dataset.models, parts=dataset.parts,
        aliases=dataset.aliases, compatibility=(), supersessions=(),
        warehouses=dataset.warehouses, transfer_routes=dataset.transfer_routes, stock=(),
    )
    with pytest.raises(fx.ScenarioError):
        fx.build_scenarios(empty)


# --- round trip through the foundation 02 fixture repository -------------

def test_committed_fixture_loads_through_repository_and_validates() -> None:
    snapshot = fx.build_catalogue(42)
    repo = FixtureCatalogueRepository.from_file(_CATALOGUE_JSON)
    assert isinstance(repo, CatalogueSource)  # satisfies the common source interface

    loaded = repo.read_version(snapshot.version_id)
    assert isinstance(loaded, CatalogueSnapshot)
    assert loaded.source == "fixture"
    assert loaded.version_id == snapshot.version_id
    assert loaded.content_sha256 == snapshot.content_sha256
    assert len(loaded.records) == len(snapshot.records)
    # foundation 02 validation passes on the loaded snapshot — zero issues
    assert validate_snapshot(loaded) == []


def test_scenario_expected_ids_resolve_against_the_committed_catalogue() -> None:
    """Every scenario's expected ids point at real records in the committed catalogue."""
    repo = FixtureCatalogueRepository.from_file(_CATALOGUE_JSON)
    snapshot = repo.read_version(fx.build_catalogue(42).version_id)
    part_keys = {r.entity_key for r in snapshot.records if r.entity_type == "parts"}
    config_keys = {r.entity_key for r in snapshot.records if r.entity_type == "model_configurations"}

    document = json.loads(_SCENARIOS_JSON.read_text(encoding="utf-8"))
    for raw in document["scenarios"]:
        scenario = DemoScenario.model_validate(raw)
        if scenario.expected_configuration_id is not None:
            assert str(scenario.expected_configuration_id) in config_keys
        for part_id in scenario.expected_part_ids:
            assert str(part_id) in part_keys


# --- synthetic marker, never real client inventory ----------------------

def test_fixtures_are_marked_synthetic() -> None:
    catalogue_doc = json.loads(_CATALOGUE_JSON.read_text(encoding="utf-8"))
    scenarios_doc = json.loads(_SCENARIOS_JSON.read_text(encoding="utf-8"))
    assert catalogue_doc["synthetic"] is True
    assert scenarios_doc["synthetic"] is True
    assert "synthetic" in catalogue_doc["provenance"].lower()
    # the scenarios must not imply real TAMGO inventory
    assert "not real tamgo inventory" in scenarios_doc["provenance"].lower()


def test_scenarios_carry_no_approved_recommendation() -> None:
    """A fixture scenario expresses expected inputs/outcomes, never an approved decision."""
    scenarios_doc = json.loads(_SCENARIOS_JSON.read_text(encoding="utf-8"))
    for raw in scenarios_doc["scenarios"]:
        assert set(raw) == {
            "id", "text", "attachment_path", "expected_status",
            "expected_configuration_id", "expected_part_ids",
        }
        assert "decision_id" not in raw and "approved_at" not in raw
        assert raw["expected_status"] in {"awaiting_review", "needs_information"}
