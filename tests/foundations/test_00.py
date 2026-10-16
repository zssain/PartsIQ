"""Acceptance tests for prompt 00 — bootstrap and preserve legacy.

Runs on the standard library only (no third-party deps), because this foundation is
what *creates* the test toolchain. The 'unauthorized' and 'stale-revision' cases from
the standard template are not applicable here: prompt 00 introduces no actor, revision
or workflow state. The applicable cases are success, invalid-input and
dependency-failure, plus the F66 safety gates (no prod DB in tests; a blocked/failed
gate is never reported as a pass).
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tools.check_release_eligibility import check_release_eligibility  # noqa: E402
from tools.verify_env import verify_environment  # noqa: E402
from tools import run_checks  # noqa: E402

SECRET = "sk-super-secret-value-0123456789abcdef"


def valid_local_env() -> dict[str, str]:
    return {
        "APP_ENV": "local",
        "DATABASE_URL": "postgresql://partsiq:pw@127.0.0.1:54322/postgres",
        "INTERNAL_SERVICE_TOKEN": "a" * 32,
        "SUPABASE_URL": "http://127.0.0.1:54321",
        "SUPABASE_JWT_ISSUER": "http://127.0.0.1:54321/auth/v1",
        "SUPABASE_JWKS_URL": "http://127.0.0.1:54321/auth/v1/.well-known/jwks.json",
        "AI_ENABLED": "false",
        "AI_PAID_BUDGET_USD": "0",
    }


class VerifyEnvironmentSuccess(unittest.TestCase):
    def test_valid_local_env_passes(self) -> None:
        self.assertEqual(verify_environment(valid_local_env()), [])


class VerifyEnvironmentInvalidInput(unittest.TestCase):
    def test_missing_required_is_reported_by_name(self) -> None:
        env = valid_local_env()
        del env["DATABASE_URL"]
        self.assertIn("DATABASE_URL", verify_environment(env))

    def test_unknown_app_env_rejected(self) -> None:
        env = valid_local_env()
        env["APP_ENV"] = "staging"
        self.assertIn("APP_ENV", verify_environment(env))

    def test_prod_database_in_local_rejected(self) -> None:
        # F66: no production database may be used by a non-production environment.
        env = valid_local_env()
        env["DATABASE_URL"] = "postgresql://u:p@db.abcdefghij.supabase.co:5432/postgres"
        self.assertIn("DATABASE_URL", verify_environment(env))

    def test_prod_database_detected_via_project_ref(self) -> None:
        env = valid_local_env()
        env["PRODUCTION_PROJECT_REF"] = "abcdefghij"
        env["DATABASE_URL"] = "postgresql://u:p@127.0.0.1:5432/abcdefghij"
        self.assertIn("DATABASE_URL", verify_environment(env))

    def test_paid_budget_must_be_zero(self) -> None:
        env = valid_local_env()
        env["AI_PAID_BUDGET_USD"] = "5"
        self.assertIn("AI_PAID_BUDGET_USD", verify_environment(env))

    def test_ai_enabled_requires_expiry(self) -> None:
        env = valid_local_env()
        env["AI_ENABLED"] = "true"
        self.assertIn("AI_CREDIT_EXPIRES_AT", verify_environment(env))


class VerifyEnvironmentNeverLeaksValues(unittest.TestCase):
    def test_only_names_are_returned(self) -> None:
        env = valid_local_env()
        del env["SUPABASE_URL"]
        env["OPENAI_API_KEY"] = SECRET
        problems = verify_environment(env)
        # The report must name the missing variable but never echo any secret value.
        self.assertIn("SUPABASE_URL", problems)
        self.assertNotIn(SECRET, problems)
        for value in env.values():
            self.assertNotIn(value, problems)

    def test_secret_in_public_variable_is_flagged(self) -> None:
        env = valid_local_env()
        env["OPENAI_API_KEY"] = SECRET
        env["NEXT_PUBLIC_LEAK"] = SECRET
        problems = verify_environment(env)
        self.assertIn("NEXT_PUBLIC_LEAK", problems)
        self.assertNotIn(SECRET, problems)


class ReleaseEligibilityGate(unittest.TestCase):
    def test_committed_receipts_are_all_eligible(self) -> None:
        self.assertEqual(check_release_eligibility(), [])

    def test_dependency_released_after_cutoff_is_rejected(self) -> None:
        # Dependency-failure case: a pin newer than the recorded cutoff must fail.
        receipts = [
            {"package": "evil", "version": "9.9.9", "released": "2099-01-01T00:00:00Z"}
        ]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(receipts, handle)
            temp_path = Path(handle.name)
        try:
            violations = check_release_eligibility(temp_path, date(2026, 9, 26))
            self.assertEqual(len(violations), 1)
            self.assertIn("evil", violations[0])
        finally:
            temp_path.unlink()


class RunChecksSafetyGates(unittest.TestCase):
    def test_refuses_production_database(self) -> None:
        # F66: tests must never run against a production database.
        import os

        saved = dict(os.environ)
        try:
            os.environ["DATABASE_URL"] = "postgresql://u:p@db.zzz.supabase.co:5432/postgres"
            os.environ.pop("APP_ENV", None)
            self.assertIsNotNone(run_checks.guard_no_prod_db())
        finally:
            os.environ.clear()
            os.environ.update(saved)

    def test_blocked_result_is_not_a_pass(self) -> None:
        # F66: a failed/blocked gate blocks deployment — exit code must be non-zero.
        self.assertEqual(run_checks.report([("missing-suite", None)]), 1)
        self.assertEqual(run_checks.report([("failed-suite", False)]), 1)
        self.assertEqual(run_checks.report([("ok-suite", True)]), 0)

    def test_missing_foundation_test_is_blocked(self) -> None:
        label, result = run_checks.run_foundation("99")
        self.assertIsNone(result)
        self.assertIn("99", label)

    def test_service_suites_cover_each_service_in_isolation(self) -> None:
        names = {name for name, _ in run_checks.SERVICE_SUITES}
        self.assertEqual(names, {"gateway", "search", "orchestrator", "worker", "catalog"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
