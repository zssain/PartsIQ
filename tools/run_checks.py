"""PartsIQ check runner.

Dispatches each test in ITS OWN process, because the four backend services all use
the ``app`` import name and cannot coexist in one interpreter (TECH_SPEC.md section 1).
It refuses to run against a production database (F66: "no prod DB in tests") and never
fabricates a passing count — a missing required test is reported as BLOCKED, not passed.

Usage:
    python tools/run_checks.py --prompt 00        # foundation test(s) for a prompt
    python tools/run_checks.py --feature F66      # a single feature's mapped test
    python tools/run_checks.py --all              # full matrix (service + UI, best effort)

At prompt 00 only the standard-library foundation tests exist; service pytest suites
and the pnpm UI suite are dispatched when their code lands in later prompts, and are
reported as SKIPPED (blocked) until then rather than counted as passing.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.verify_env import _looks_like_production  # noqa: E402  (local tool import)

FOUNDATIONS = REPO_ROOT / "tests" / "foundations"
FEATURES_SPEC = REPO_ROOT / "spec" / "features.json"

# Legacy + new service test suites, each run in its own process (pytest).
SERVICE_SUITES: tuple[tuple[str, str], ...] = (
    ("gateway", "services/gateway"),
    ("search", "services/search"),
    ("orchestrator", "services/orchestrator"),
    ("worker", "services/worker"),
    ("catalog", "tools/catalog"),
)


def guard_no_prod_db() -> str | None:
    """Return a refusal message if the ambient env would let tests touch prod."""
    app_env = (os.environ.get("APP_ENV") or "test").strip().lower()
    if app_env == "production":
        return "APP_ENV=production: refusing to run tests against a production environment."
    prod_ref = os.environ.get("PRODUCTION_PROJECT_REF")
    for name in ("DATABASE_URL", "MIGRATION_DATABASE_URL"):
        url = os.environ.get(name)
        if url and _looks_like_production(url, prod_ref):
            return f"{name} points at a production database: refusing to run tests."
    return None


def _run(cmd: list[str], cwd: Path) -> bool:
    """Run one test command in its own process; stream output; return success."""
    print(f"\n$ ({cwd.relative_to(REPO_ROOT)}) {' '.join(cmd)}", flush=True)
    env = dict(os.environ)
    env.setdefault("APP_ENV", "test")
    completed = subprocess.run(cmd, cwd=str(cwd), env=env)
    return completed.returncode == 0


def run_foundation(prompt: str) -> tuple[str, bool | None]:
    """Run tests/foundations/test_<prompt>.py (stdlib unittest). None = blocked/missing."""
    path = FOUNDATIONS / f"test_{prompt}.py"
    label = f"foundations/test_{prompt}.py"
    if not path.exists():
        return label, None
    return label, _run([sys.executable, str(path)], cwd=REPO_ROOT)


def resolve_feature_test(feature: str) -> Path | None:
    """Map a feature id (e.g. F66) to its test path via spec/features.json."""
    if not FEATURES_SPEC.exists():
        return None
    data = json.loads(FEATURES_SPEC.read_text(encoding="utf-8"))
    entries = data.values() if isinstance(data, dict) else data
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("id", "")).upper() == feature.upper():
            test = entry.get("test")
            if test:
                return REPO_ROOT / test
    return None


def run_service_suites() -> list[tuple[str, bool | None]]:
    """Best-effort: run each service's pytest suite in its own process."""
    results: list[tuple[str, bool | None]] = []
    try:
        import pytest  # noqa: F401
    except ImportError:
        for name, _ in SERVICE_SUITES:
            results.append((f"service:{name} (pytest unavailable)", None))
        return results
    for name, rel in SERVICE_SUITES:
        suite = REPO_ROOT / rel
        if not (suite / "tests").exists():
            results.append((f"service:{name} (no tests yet)", None))
            continue
        results.append((f"service:{name}", _run([sys.executable, "-m", "pytest", "-q"], cwd=suite)))
    return results


def report(results: list[tuple[str, bool | None]]) -> int:
    print("\n" + "=" * 60)
    print("run_checks summary")
    print("=" * 60)
    passed = failed = blocked = 0
    for label, ok in results:
        if ok is True:
            status, _ = "PASS", passed
            passed += 1
        elif ok is False:
            status = "FAIL"
            failed += 1
        else:
            status = "BLOCKED"
            blocked += 1
        print(f"  [{status:7}] {label}")
    print(f"\n  passed={passed} failed={failed} blocked={blocked}")
    # A blocked REQUIRED test is not a pass: any failure or block is a non-zero exit.
    return 0 if (failed == 0 and blocked == 0) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PartsIQ check runner")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prompt", help="foundation prompt id, e.g. 00")
    group.add_argument("--feature", help="feature id, e.g. F66")
    group.add_argument("--all", action="store_true", help="run the full matrix")
    args = parser.parse_args(argv)

    refusal = guard_no_prod_db()
    if refusal:
        print(f"REFUSED: {refusal}", file=sys.stderr)
        return 2

    results: list[tuple[str, bool | None]] = []

    if args.prompt:
        results.append(run_foundation(args.prompt))
    elif args.feature:
        test = resolve_feature_test(args.feature)
        if test is None or not test.exists():
            results.append((f"feature:{args.feature} (test not implemented yet)", None))
        else:
            results.append((f"feature:{args.feature}", _run([sys.executable, str(test)], cwd=REPO_ROOT)))
    else:  # --all
        for prompt_file in sorted(FOUNDATIONS.glob("test_*.py")):
            results.append(run_foundation(prompt_file.stem.removeprefix("test_")))
        results.extend(run_service_suites())

    return report(results)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
