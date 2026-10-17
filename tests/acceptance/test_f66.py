"""F66 Tests and CI — service-isolated tests, frontend checks, RLS integration, evals; gated deploy.

No production DB in tests; no secret reaches untrusted fork jobs; a failed gate blocks
deployment (activation needs the migration job and the INFRA_READY flag).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tools.ci_checks import check_ci_configuration  # noqa: E402

WF = REPO_ROOT / ".github" / "workflows"


def _load(name: str) -> dict:
    return yaml.safe_load((WF / name).read_text(encoding="utf-8"))


class TestsAndCi(unittest.TestCase):
    def test_configuration_is_compliant(self):
        self.assertEqual(check_ci_configuration(REPO_ROOT), [])

    def test_ci_runs_all_required_check_kinds(self):
        jobs = _load("ci.yml")["jobs"]
        self.assertIn("python-tests", jobs)
        self.assertIn("frontend", jobs)
        self.assertIn("rls-integration", jobs)
        self.assertIn("evals", jobs)
        # Service isolation: the python-tests job runs per-suite in a matrix.
        self.assertIn("suite", jobs["python-tests"]["strategy"]["matrix"])

    def test_no_prod_db_in_tests(self):
        ci = _load("ci.yml")
        self.assertEqual(ci["env"]["APP_ENV"], "test")

    def test_deploy_not_exposed_to_fork_pull_requests(self):
        deploy = _load("deploy-backend.yml")
        on = deploy.get("on") or deploy.get(True)
        self.assertNotIn("pull_request", on)
        self.assertNotIn("pull_request_target", on)

    def test_failed_gate_blocks_deployment(self):
        jobs = _load("deploy-backend.yml")["jobs"]
        self.assertIn("migrate", jobs["deploy"]["needs"])        # migration precedes activation
        self.assertIn("INFRA_READY", str(jobs["deploy"].get("if")))  # disabled until ready


if __name__ == "__main__":
    unittest.main(verbosity=2)
