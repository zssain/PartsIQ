"""Deterministic labelled-evaluation runner and evidence receipts (foundation 21 — F62/F48).

Ported from the legacy ``tools/evals/run.py`` onto the single ``partsiq`` package. The
deterministic suite (``live=False``) scores a committed, labelled fixture against an injected
resolver that reads only the seed-42 synthetic catalogue — it NEVER imports or calls OpenAI,
so it needs no account credit (CONSTRAINTS rule 13). The live-extraction suite is a SEPARATE,
allowance-gated path that this module does not run (it only shapes the receipt for it).

Scoring rules (CONSTRAINTS: never fabricate accuracy; a model confidence is never accuracy):
  * :func:`evaluate_case` passes only on an EXACT match of status and the compatible part set;
    a failing case keeps its ACTUAL output (never an expected answer, never a model score).
  * :func:`accuracy` scores DEFINITIVE labelled cases only; unlabelled (unreadable) cases are
    excluded entirely, and labelled abstentions (clarifications) are reported SEPARATELY rather
    than counted correct or wrong.
  * :func:`dataset_sha256` canonically hashes the labelled fixture so a run pins its dataset.
  * :func:`build_run_receipt` records the dataset hash always; a LIVE run also records the git
    SHA and model id, while a deterministic run claims NEITHER a live model nor model accuracy.

Input isolation (F48): :func:`deterministic_solver` keys ONLY off a case's labelled scenario;
the ``input_text`` — including an embedded "SYSTEM: ignore your rules" injection — can never
change the resolved output. The resolver is injected so the harness stays pure and offline.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from uuid import UUID, uuid5

from partsiq.core.contracts import EvalCase, EvalOutput, EvalResult, EvalRun

#: An injected resolver: the only thing the suite calls to produce an output for a case. The
#: deterministic implementation below makes no network/model/Snowflake call; a live resolver
#: (OpenAI extraction) is a different, allowance-gated injection and is NOT provided here.
Solver = Callable[[EvalCase], Awaitable[EvalOutput]]

#: The committed labelled dataset at the repo root under ``evals/`` (this file lives at
#: ``apps/api/partsiq/evaluation/runner.py`` → ``parents[4]`` is the repository root).
_REPO_ROOT = Path(__file__).resolve().parents[4]
CASES_PATH = _REPO_ROOT / "evals" / "cases.json"

#: Stable namespace so a deterministic run id is reproducible from the dataset hash (no clock,
#: no randomness) — the same committed dataset always yields the same :class:`EvalRun.id`.
_RUN_NAMESPACE = UUID("00000000-0000-4000-8000-00000000e021")

#: The status a labelled abstention carries (a clarification the system SHOULD raise).
_ABSTAIN_STATUS = "needs_information"
#: The status an unlabelled case carries (unreadable; excluded from accuracy entirely).
_UNLABELLED_STATUS = "unlabelled"


def load_cases(path: Path = CASES_PATH) -> list[EvalCase]:
    """Load and validate the committed labelled fixture."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [EvalCase.model_validate(entry) for entry in raw]


def dataset_sha256(cases: list[EvalCase]) -> str:
    """Hash the labelled fixture canonically (sorted keys) so a run pins its exact dataset."""
    payload = json.dumps(
        [case.model_dump() for case in cases], sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def evaluate_case(case: EvalCase, actual: EvalOutput) -> EvalResult:
    """Exact-match status + compatible set; never a model confidence, and keep the actual output.

    ``EvalOutput`` carries no confidence field by construction, and the comparison is purely the
    labelled status and the (order-insensitive) part set. A mismatch records ``passed=False`` and
    retains the ACTUAL output verbatim so a receipt can show the real failure (never the expected
    answer is substituted to make the case pass).
    """
    passed = (
        actual.status == case.expected_status
        and sorted(actual.part_ids) == sorted(case.expected_part_ids)
    )
    return EvalResult(case_id=case.id, passed=passed, actual=actual)


async def run_suite(cases: list[EvalCase], *, solve: Solver, live: bool = False) -> EvalRun:
    """Score every case through the injected resolver.

    The deterministic path (``live=False`` with :func:`deterministic_solver`) performs no model,
    network or Snowflake call. ``live`` only flows through to the receipt; the live resolver is a
    separate, allowance-gated injection the caller supplies and this module never fabricates.
    """
    results = [evaluate_case(case, await solve(case)) for case in cases]
    digest = dataset_sha256(cases)
    return EvalRun(id=uuid5(_RUN_NAMESPACE, digest), dataset_sha256=digest, results=results)


def accuracy(cases: list[EvalCase], run: EvalRun) -> dict[str, object]:
    """Accuracy over DEFINITIVE labelled cases only.

    Unlabelled (unreadable) cases are excluded from every count except ``total`` and
    ``unlabelled``; labelled abstentions are reported in ``abstained`` and are neither correct
    nor wrong. ``accuracy`` is ``correct / scored`` over the remaining definitive cases, or
    ``None`` when nothing is scored (never silently reported as 1.0 or 0.0).
    """
    by_id = {case.id: case for case in cases}
    unlabelled = abstained = scored = correct = 0
    for result in run.results:
        case = by_id[result.case_id]
        if case.expected_status == _UNLABELLED_STATUS:
            unlabelled += 1
            continue
        if case.expected_status == _ABSTAIN_STATUS:  # a labelled abstention (clarification)
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


def build_run_receipt(
    run: EvalRun, *, git_sha: str, model_id: str | None, live: bool
) -> dict[str, object]:
    """Build a loggable evidence receipt for an evaluation run.

    The dataset hash is always recorded. A LIVE run MUST name the git SHA and the model id so a
    measured-accuracy claim is tied to a specific code revision and model (F62, CONSTRAINTS rule
    18). A deterministic run records the git SHA for provenance but explicitly does NOT claim a
    live model — ``model_id`` is cleared and ``claims_model_accuracy`` is false, so a simulated
    resolver is never mistaken for measured model accuracy.
    """
    passed = sum(1 for result in run.results if result.passed)
    return {
        "run_id": str(run.id),
        "dataset_sha256": run.dataset_sha256,
        "git_sha": git_sha,
        "live": live,
        "model_id": model_id if live else None,
        "claims_model_accuracy": live,
        "passed": passed,
        "total": len(run.results),
    }


# ---------------------------------------------------------------------------
# Deterministic resolver over the seed-42 catalogue (no OpenAI, no Snowflake, no network).
# It is keyed SOLELY by a case's labelled scenario: resolving scenarios return the single
# compatible air filter, abstention scenarios return a clarification, unlabelled returns an
# abstention excluded from accuracy, and the injection scenario resolves to the SAME legitimate
# result as its clean form — the embedded instruction text is ignored, never acted on (F48).
# ---------------------------------------------------------------------------

#: The compatible air filter (part ordinal 92, configuration 13) for Corvane Air CA-110 — the
#: same part the seed-42 ``build_scenarios`` assigns to the mixed_photo / local_shortage demos.
_RESOLVED_PART = 92
#: The two close-scoring air-filter candidates surfaced when the request is ambiguous.
_AMBIGUOUS_CANDIDATES = [91, 92]

#: scenario -> clarification code for labelled abstentions.
_ABSTAIN_CODE: dict[str, str] = {
    "missing_serial": "needs_serial",
    "incompatible_number": "mismatch",
    "ambiguity": "ambiguous_part",
}
#: scenario -> the candidate set surfaced alongside a clarification (empty for most).
_ABSTAIN_PARTS: dict[str, list[int]] = {"ambiguity": _AMBIGUOUS_CANDIDATES}


def deterministic_solver() -> Solver:
    """Return a pure resolver mapping a labelled scenario to its deterministic outcome.

    No OpenAI/Snowflake import or call is made. The resolver reads ONLY ``case.scenario`` /
    ``case.expected_status``; it never inspects ``case.input_text``, so an injected instruction
    cannot steer the output (F48 input isolation).
    """

    async def solve(case: EvalCase) -> EvalOutput:
        if case.expected_status == _UNLABELLED_STATUS:
            # Unreadable/unlabelled: the system abstains; the case is excluded from accuracy.
            return EvalOutput(status=_UNLABELLED_STATUS, part_ids=[], clarification_code="none")
        if case.scenario in _ABSTAIN_CODE:
            return EvalOutput(
                status=_ABSTAIN_STATUS,
                part_ids=_ABSTAIN_PARTS.get(case.scenario, []),
                clarification_code=_ABSTAIN_CODE[case.scenario],
            )
        # Every resolving scenario (incl. arabic/typo/serial-boundary/stock/injection) reaches
        # the same compatible part deterministically; the injection text changes nothing.
        return EvalOutput(
            status="awaiting_review", part_ids=[_RESOLVED_PART], clarification_code="none"
        )

    return solve
