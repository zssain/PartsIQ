"""Deterministic evaluation suite (prompt 21 — F62).

Validates the labelled fixture against catalogue truth and the harness accounting WITHOUT any
model call: the four demo labels are re-derived from the seed-42 catalogue via build_scenarios,
and the deterministic resolver reproduces every label (accuracy 1.0, abstentions reported
separately). Standalone so it runs without the pnpm/service runner.
"""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT, REPO_ROOT / "libs" / "partsiq_common", REPO_ROOT / "tools" / "demo", REPO_ROOT / "tools" / "catalog"):
    sys.path.insert(0, str(p))

import build_scenarios as bs  # noqa: E402

from catalog.generator import generate_catalog  # noqa: E402
from tools.evals.run import accuracy, deterministic_solver, load_cases, run_suite  # noqa: E402

CASES = load_cases()
BY_SCENARIO = {c.scenario: c for c in CASES}


class DemoLabelsMatchCatalogue(unittest.TestCase):
    def test_four_demo_labels_match_build_scenarios(self):
        scenarios = {s.id: s for s in bs.build_scenarios(generate_catalog(42))}
        for demo_id in ("mixed_photo", "missing_serial", "incompatible_number", "local_shortage"):
            case = BY_SCENARIO[demo_id]
            truth = scenarios[demo_id]
            self.assertEqual(case.expected_status, truth.expected_status, demo_id)
            self.assertEqual(sorted(case.expected_part_ids), sorted(truth.expected_part_ids), demo_id)


class DeterministicRun(unittest.TestCase):
    def test_resolver_reproduces_every_label(self):
        run = asyncio.run(run_suite(CASES, live=False, solve=deterministic_solver()))
        failed = [r.case_id for r in run.results if not r.passed]
        self.assertEqual(failed, [])

    def test_accuracy_is_one_with_abstentions_reported(self):
        run = asyncio.run(run_suite(CASES, live=False, solve=deterministic_solver()))
        acc = accuracy(CASES, run)
        self.assertEqual(acc["accuracy"], 1.0)
        self.assertGreaterEqual(acc["abstained"], 3)
        self.assertGreaterEqual(acc["unlabelled"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
