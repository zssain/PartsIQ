"""F02 Demo scenarios and assets — four deterministic seed-42 scenarios, validated.

Invokes the production entry points (build_scenarios/validate_scenarios over a seed-42
CatalogDataset): the four scenarios are present and deterministic, validation accepts them,
and it REJECTS a scenario whose expected part is incompatible or whose stock claim is
unsupported. The committed scenario files match the generated scenarios.
"""
from __future__ import annotations

import sys
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


class DemoScenarios(unittest.TestCase):
    def test_four_deterministic_scenarios(self):  # success
        self.assertEqual(set(BY_ID), {"mixed_photo", "missing_serial", "incompatible_number", "local_shortage"})
        again = bs.build_scenarios(generate_catalog(42))
        self.assertEqual([s.model_dump() for s in again], [s.model_dump() for s in SCENARIOS])

    def test_generated_scenarios_validate(self):
        self.assertEqual(bs.validate_scenarios(SCENARIOS, DATASET), [])

    def test_rejects_incompatible_expected_part(self):  # invalid-input
        parts = bs.part_ordinals(DATASET)
        configs = bs.configuration_ordinals(DATASET)
        compat = bs._compat_set(DATASET)
        config_key = {v: k for k, v in configs.items()}[BY_ID["mixed_photo"].expected_configuration_id]
        bad = next(parts[p.part_number] for p in DATASET.parts if (p.part_number, *config_key) not in compat)
        tampered = BY_ID["mixed_photo"].model_copy(update={"expected_part_ids": [bad]})
        self.assertTrue(any("not compatible" in e for e in bs.validate_scenarios([tampered], DATASET)))

    def test_rejects_unsupported_stock_claim(self):
        parts = bs.part_ordinals(DATASET)
        stock = bs._stock_by_part(DATASET)
        stocked = next(
            parts[number] for number, levels in stock.items()
            if all(level.quantity_on_hand - level.quantity_reserved > 0 for level in levels)
        )
        tampered = BY_ID["local_shortage"].model_copy(update={"expected_part_ids": [stocked]})
        self.assertTrue(any("stock claim" in e for e in bs.validate_scenarios([tampered], DATASET)))

    def test_committed_scenarios_match(self):
        for scenario in SCENARIOS:
            raw = (REPO_ROOT / "tools" / "demo" / "scenarios" / f"{scenario.id}.json").read_text(encoding="utf-8")
            self.assertEqual(DemoScenario.model_validate_json(raw).model_dump(), scenario.model_dump())


if __name__ == "__main__":
    unittest.main(verbosity=2)
