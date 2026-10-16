"""Acceptance tests for prompt 05 — synthetic catalogue and demo fixtures.

Deterministic + offline: the four scenarios are derived from real seed-42 records,
validation accepts them, and it REJECTS a scenario whose expected part is not
compatible or whose stock claim is unsupported (F02). render_nameplate produces a real
PNG. Loading the catalogue into a database is a separate base-load step (BLOCKED here).
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools" / "demo"))
sys.path.insert(0, str(REPO_ROOT / "tools" / "catalog"))
sys.path.insert(0, str(REPO_ROOT / "libs" / "partsiq_common"))

import build_scenarios as bs  # noqa: E402

from catalog.generator import generate_catalog  # noqa: E402
from partsiq_common.contracts import DemoScenario  # noqa: E402

DATASET = generate_catalog(42)
SCENARIOS = bs.build_scenarios(DATASET)
BY_ID = {s.id: s for s in SCENARIOS}


class BuildScenarios(unittest.TestCase):
    def test_all_four_scenarios_present(self) -> None:
        self.assertEqual(set(BY_ID), {"mixed_photo", "missing_serial", "incompatible_number", "local_shortage"})

    def test_deterministic(self) -> None:
        again = bs.build_scenarios(generate_catalog(42))
        self.assertEqual([s.model_dump() for s in again], [s.model_dump() for s in SCENARIOS])

    def test_scenario_shapes(self) -> None:
        self.assertIsNotNone(BY_ID["mixed_photo"].attachment_path)
        self.assertTrue(BY_ID["mixed_photo"].expected_part_ids)
        self.assertIsNone(BY_ID["missing_serial"].expected_configuration_id)
        self.assertEqual(BY_ID["missing_serial"].expected_part_ids, [])
        self.assertEqual(BY_ID["incompatible_number"].expected_part_ids, [])
        self.assertIsNotNone(BY_ID["incompatible_number"].expected_configuration_id)
        self.assertTrue(BY_ID["local_shortage"].expected_part_ids)


class ValidateScenarios(unittest.TestCase):
    def test_generated_scenarios_are_valid(self) -> None:
        self.assertEqual(bs.validate_scenarios(SCENARIOS, DATASET), [])

    def test_rejects_incompatible_expected_part(self) -> None:  # F02
        parts = bs.part_ordinals(DATASET)
        configs = bs.configuration_ordinals(DATASET)
        compat = bs._compat_set(DATASET)
        config_key = {v: k for k, v in configs.items()}[BY_ID["mixed_photo"].expected_configuration_id]
        bad_ordinal = next(
            parts[p.part_number]
            for p in DATASET.parts
            if (p.part_number, *config_key) not in compat
        )
        tampered = BY_ID["mixed_photo"].model_copy(update={"expected_part_ids": [bad_ordinal]})
        errors = bs.validate_scenarios([tampered], DATASET)
        self.assertTrue(any("not compatible" in e for e in errors))

    def test_rejects_unsupported_stock_claim(self) -> None:  # F02
        parts = bs.part_ordinals(DATASET)
        stock = bs._stock_by_part(DATASET)
        fully_stocked = next(
            parts[number]
            for number, levels in stock.items()
            if all(level.quantity_on_hand - level.quantity_reserved > 0 for level in levels)
        )
        tampered = BY_ID["local_shortage"].model_copy(update={"expected_part_ids": [fully_stocked]})
        errors = bs.validate_scenarios([tampered], DATASET)
        self.assertTrue(any("stock claim" in e for e in errors))


class RenderNameplate(unittest.TestCase):
    def test_renders_png(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "plate.png"
            bs.render_nameplate("CA-110", "800000", dest)
            self.assertTrue(dest.exists())
            self.assertEqual(dest.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
            self.assertGreater(dest.stat().st_size, 0)


class CommittedFixtures(unittest.TestCase):
    def test_committed_scenarios_match_build(self) -> None:
        for scenario in SCENARIOS:
            raw = (REPO_ROOT / "tools" / "demo" / "scenarios" / f"{scenario.id}.json").read_text(encoding="utf-8")
            on_disk = DemoScenario.model_validate_json(raw)
            self.assertEqual(on_disk.model_dump(), scenario.model_dump())

    def test_manifests_record_hashes(self) -> None:
        for manifest in ("nameplates/manifest.json", "catalogue_evidence/manifest.json"):
            data = json.loads((REPO_ROOT / "tools" / "demo" / manifest).read_text(encoding="utf-8"))
            self.assertEqual(data["seed"], 42)
            self.assertTrue(all(len(a["sha256"]) == 64 for a in data["assets"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
