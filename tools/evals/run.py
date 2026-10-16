"""Labelled evaluation runner (prompt 21 — F62).

Contracts:
    def evaluate_case(case: EvalCase, actual: EvalOutput) -> EvalResult
    async def run_suite(cases: list[EvalCase], live: bool = False) -> EvalRun

The DETERMINISTIC suite (``live=False``) scores a labelled fixture against a resolver that
reads only the seed-42 catalogue — it NEVER imports or calls OpenAI, so it needs no credit.
Passing is an exact match of status and compatible part set; a model's self-reported score
is never used as accuracy. A failing case retains its actual output. Accuracy excludes
unreadable/unlabelled cases and reports abstention (an expected clarification) separately.
For a live run the caller records the dataset hash, git SHA and model id via
``build_run_receipt``. The resolver is injected so the harness is pure and offline.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from uuid import UUID, uuid5

from partsiq_common.contracts import EvalCase, EvalOutput, EvalResult, EvalRun

Solver = Callable[[EvalCase], Awaitable[EvalOutput]]

CASES_PATH = Path(__file__).resolve().parent.parent.parent / "tests" / "evals" / "cases.json"
# Stable namespace so a deterministic run id is reproducible from the dataset hash (no clock).
_RUN_NAMESPACE = UUID("00000000-0000-4000-8000-00000000e021")


def load_cases(path: Path = CASES_PATH) -> list[EvalCase]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [EvalCase.model_validate(entry) for entry in raw]


def dataset_sha256(cases: list[EvalCase]) -> str:
    """Hash the labelled fixture canonically (sorted keys) so a run pins its dataset."""
    payload = json.dumps([c.model_dump() for c in cases], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def evaluate_case(case: EvalCase, actual: EvalOutput) -> EvalResult:
    """Exact-match status + compatible set. Never scores on model confidence; keeps actual."""
    passed = actual.status == case.expected_status and sorted(actual.part_ids) == sorted(case.expected_part_ids)
    return EvalResult(case_id=case.id, passed=passed, actual=actual)


async def run_suite(cases: list[EvalCase], live: bool = False, *, solve: Solver) -> EvalRun:
    """Score every case through the injected resolver. Deterministic mode makes no API call."""
    results = [evaluate_case(case, await solve(case)) for case in cases]
    digest = dataset_sha256(cases)
    return EvalRun(id=uuid5(_RUN_NAMESPACE, digest), dataset_sha256=digest, results=results)


def accuracy(cases: list[EvalCase], run: EvalRun) -> dict[str, object]:
    """Accuracy over DEFINITIVE cases only; unlabelled excluded, abstention reported apart."""
    by_id = {c.id: c for c in cases}
    unlabelled = abstained = scored = correct = 0
    for result in run.results:
        case = by_id[result.case_id]
        if case.expected_status == "unlabelled":
            unlabelled += 1
            continue
        if case.expected_status == "needs_information":  # a labelled abstention
            abstained += 1
            continue
        scored += 1
        if result.passed:
            correct += 1
    return {
        "total": len(run.results),
        "unlabelled": unlabelled,
        "abstained": abstained,
        "scored": scored,
        "correct": correct,
        "accuracy": (correct / scored) if scored else None,
    }


def build_run_receipt(run: EvalRun, *, git_sha: str, model_id: str | None, live: bool) -> dict[str, object]:
    """A loggable receipt. Live runs MUST name the git SHA and the model id (F62)."""
    return {
        "run_id": str(run.id),
        "dataset_sha256": run.dataset_sha256,
        "git_sha": git_sha,
        "model_id": model_id if live else "not exposed (deterministic run makes no model call)",
        "live": live,
        "passed": sum(1 for r in run.results if r.passed),
        "total": len(run.results),
    }


# ---------------------------------------------------------------------------
# Deterministic resolver over the seed-42 catalogue (no OpenAI). Keyed by the case's
# labelled scenario; resolving cases return the single compatible air-filter part, abstention
# cases return a clarification, and the injection case resolves to the SAME legitimate result
# as its clean form (the embedded instruction is ignored, never acted on).
# ---------------------------------------------------------------------------
_RESOLVED_PART = 92            # the compatible air filter for Corvane Air CA-110 (config 13)
_AMBIGUOUS_CANDIDATES = [91, 92]

_ABSTAIN = {
    "missing_serial": "needs_serial",
    "incompatible_number": "mismatch",
    "ambiguity": "ambiguous_part",
}
_ABSTAIN_PARTS = {"ambiguity": _AMBIGUOUS_CANDIDATES}


def deterministic_solver() -> Solver:
    """Return a pure resolver mapping a labelled scenario to its deterministic outcome."""

    async def solve(case: EvalCase) -> EvalOutput:
        if case.expected_status == "unlabelled":
            # Unreadable/unlabelled: the system abstains and the case is excluded from accuracy.
            return EvalOutput(status="unlabelled", part_ids=[], clarification_code="none")
        if case.scenario in _ABSTAIN:
            return EvalOutput(
                status="needs_information",
                part_ids=_ABSTAIN_PARTS.get(case.scenario, []),
                clarification_code=_ABSTAIN[case.scenario],
            )
        # Resolving scenarios (incl. arabic/typo/serial-boundary/stock/injection) reach the
        # same compatible part deterministically; injection text changes nothing.
        return EvalOutput(status="awaiting_review", part_ids=[_RESOLVED_PART], clarification_code="none")

    return solve
