"""Acceptance tests for prompt 21 — labelled evaluations (foundation gate).

The deterministic evaluation harness scores a labelled fixture without any OpenAI call:
evaluate_case is an exact status+compat match (never a model confidence), a failing case
keeps its actual output, run_suite pins the dataset hash, accuracy excludes unlabelled cases
and reports abstention separately, and a live receipt records the git SHA and model id.
Covers F62.
"""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "libs" / "partsiq_common"))

from partsiq_common.contracts import EvalCase, EvalOutput  # noqa: E402
from tools.evals.run import (  # noqa: E402
    accuracy,
    build_run_receipt,
    dataset_sha256,
    deterministic_solver,
    evaluate_case,
    load_cases,
    run_suite,
)

REQUIRED_SCENARIOS = {
    "mixed_photo", "missing_serial", "incompatible_number", "local_shortage",
    "arabic_normalization", "typo_tolerance", "serial_boundary", "ambiguity",
    "multi_item_stock", "injection",
}


def _case(scenario="injection", status="awaiting_review", parts=(92,)):
    return EvalCase(id="c1", scenario=scenario, input_text="x", expected_status=status, expected_part_ids=list(parts))


class EvaluateCase(unittest.TestCase):
    def test_exact_match_passes(self):
        case = _case()
        result = evaluate_case(case, EvalOutput(status="awaiting_review", part_ids=[92], clarification_code="none"))
        self.assertTrue(result.passed)

    def test_mismatch_fails_and_keeps_actual(self):
        case = _case()
        actual = EvalOutput(status="needs_information", part_ids=[], clarification_code="needs_serial")
        result = evaluate_case(case, actual)
        self.assertFalse(result.passed)
        self.assertEqual(result.actual, actual)  # failures retain the actual output (F62)


class Fixture(unittest.TestCase):
    def test_all_required_categories_present(self):
        scenarios = {c.scenario for c in load_cases()}
        self.assertTrue(REQUIRED_SCENARIOS.issubset(scenarios), REQUIRED_SCENARIOS - scenarios)

    def test_deterministic_suite_needs_no_openai(self):
        # The harness imports neither OpenAI nor the shared model client (prose mentions are ok).
        source = (REPO_ROOT / "tools" / "evals" / "run.py").read_text(encoding="utf-8")
        self.assertNotIn("import openai", source)
        self.assertNotIn("from openai", source)
        self.assertNotIn("call_structured", source)


class RunSuite(unittest.TestCase):
    def test_deterministic_run_passes_and_pins_dataset(self):
        cases = load_cases()
        run = asyncio.run(run_suite(cases, live=False, solve=deterministic_solver()))
        self.assertEqual(run.dataset_sha256, dataset_sha256(cases))
        self.assertTrue(all(r.passed for r in run.results), [r.case_id for r in run.results if not r.passed])

    def test_accuracy_excludes_unlabelled_and_reports_abstention(self):
        cases = load_cases()
        run = asyncio.run(run_suite(cases, live=False, solve=deterministic_solver()))
        acc = accuracy(cases, run)
        self.assertGreaterEqual(acc["unlabelled"], 1)     # the unreadable case excluded
        self.assertGreaterEqual(acc["abstained"], 3)      # missing_serial, incompatible, ambiguity
        self.assertEqual(acc["correct"], acc["scored"])   # deterministic resolver is correct
        self.assertEqual(acc["accuracy"], 1.0)

    def test_live_receipt_records_git_sha_and_model(self):
        cases = load_cases()
        run = asyncio.run(run_suite(cases, live=False, solve=deterministic_solver()))
        live = build_run_receipt(run, git_sha="abc1234", model_id="gpt-4.1-mini-2025-04-14", live=True)
        self.assertEqual(live["git_sha"], "abc1234")
        self.assertEqual(live["model_id"], "gpt-4.1-mini-2025-04-14")
        offline = build_run_receipt(run, git_sha="abc1234", model_id=None, live=False)
        self.assertIn("not exposed", str(offline["model_id"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
