"""F62 Labelled evaluations — four demos plus Arabic/typo/serial/ambiguity/stock/injection.

The fixture covers the required categories, records the expected compatible set and
clarification outcome, runs deterministically without API calls, never uses a self-reported
model confidence as accuracy, keeps actual output on failure, and is disjoint from any
example embedded in the LLM prompt templates.
"""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "libs" / "partsiq_common"))

from partsiq_common.contracts import EvalOutput  # noqa: E402
from tools.evals.run import deterministic_solver, evaluate_case, load_cases, run_suite  # noqa: E402

CASES = load_cases()


class LabelledEvaluations(unittest.TestCase):
    def test_required_categories_present(self):
        scenarios = {c.scenario for c in CASES}
        for required in (
            "mixed_photo", "missing_serial", "incompatible_number", "local_shortage",
            "arabic_normalization", "typo_tolerance", "serial_boundary", "ambiguity",
            "multi_item_stock", "injection",
        ):
            self.assertIn(required, scenarios)

    def test_accuracy_never_uses_model_confidence(self):
        # EvalOutput carries no confidence field, and evaluate_case compares only status + parts.
        self.assertNotIn("confidence", EvalOutput.model_fields)
        case = CASES[0]
        wrong = EvalOutput(status="needs_information", part_ids=[], clarification_code="needs_serial")
        self.assertFalse(evaluate_case(case, wrong).passed)

    def test_failure_keeps_actual_output(self):
        case = CASES[0]
        actual = EvalOutput(status="failed", part_ids=[999], clarification_code=None)
        result = evaluate_case(case, actual)
        self.assertFalse(result.passed)
        self.assertEqual(result.actual.part_ids, [999])

    def test_fixture_disjoint_from_prompt_examples(self):
        prompts = (REPO_ROOT / "services" / "orchestrator" / "app" / "prompts")
        prompt_text = "\n".join(p.read_text(encoding="utf-8") for p in prompts.glob("*.txt"))
        for case in CASES:
            self.assertNotIn(case.input_text, prompt_text)  # no eval input leaked into a prompt

    def test_runs_deterministically(self):
        run = asyncio.run(run_suite(CASES, live=False, solve=deterministic_solver()))
        self.assertEqual(len(run.results), len(CASES))
        self.assertTrue(all(r.passed for r in run.results))


if __name__ == "__main__":
    unittest.main(verbosity=2)
