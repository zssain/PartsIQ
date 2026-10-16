"""Labelled evaluation harness (prompt 21).

Public API: evaluate_case, run_suite, accuracy, dataset_sha256, build_run_receipt,
deterministic_solver. The deterministic suite never imports or calls OpenAI.
"""

from tools.evals.run import (
    accuracy,
    build_run_receipt,
    dataset_sha256,
    deterministic_solver,
    evaluate_case,
    load_cases,
    run_suite,
)

__all__ = [
    "accuracy",
    "build_run_receipt",
    "dataset_sha256",
    "deterministic_solver",
    "evaluate_case",
    "load_cases",
    "run_suite",
]
