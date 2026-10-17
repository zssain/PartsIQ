"""Prompt 25 acceptance — CI, reproducible builds and release checks (offline static checks).

These tests NEVER run GitHub Actions, build an image or assume an AWS role (all BLOCKED). They
parse the committed single-workflow YAML and exercise the static checker so the security
posture is verifiable from a plain `git checkout`:

  * every third-party action in both workflows is pinned to a 40-hex commit SHA (not @vN / a
    branch), making builds reproducible;
  * each workflow declares least-privilege top-level `permissions: contents: read`;
  * the CI workflow runs the service-isolated apps/api pytest suite under
    `uv run --all-packages`, with APP_ENV=test, plus ruff, the frontend lint/typecheck/vitest
    checks and the deterministic evaluation harness;
  * the deploy workflow is `workflow_dispatch` ONLY (never pull_request / pull_request_target),
    requires the `production` GitHub environment (manual approval), authenticates to AWS via
    OIDC (`id-token: write`) with no static AWS keys, runs the migration job BEFORE image
    activation, and keeps activation gated on the INFRA_READY flag (off until prompt 26);
  * the static checker tools/ci_checks.check_ci_configuration flags each of those failures in a
    deliberately broken config.

Coexistence note: the earlier multi-service build owns `.github/workflows/ci.yml` and
`deploy-backend.yml`; this prompt adds the single-package `ci-partsiq.yml` /
`deploy-partsiq.yml` and these tests target ONLY those new filenames.
"""
from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
CI_PATH = WORKFLOWS / "ci-partsiq.yml"
DEPLOY_PATH = WORKFLOWS / "deploy-partsiq.yml"

sys.path.insert(0, str(REPO_ROOT))
from tools.ci_checks import check_ci_configuration  # noqa: E402

_SHA_PINNED = re.compile(r"^[A-Za-z0-9._/-]+@[0-9a-f]{40}$")


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _uses_values(node) -> list[str]:
    """Collect every `uses:` value anywhere in the workflow tree."""
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "uses" and isinstance(value, str):
                found.append(value)
            else:
                found.extend(_uses_values(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_uses_values(item))
    return found


def _triggers(wf: dict) -> dict:
    # PyYAML parses the bare key `on:` as the boolean True.
    on = wf.get("on")
    if on is None:
        on = wf.get(True) or {}
    if isinstance(on, dict):
        return on
    if isinstance(on, list):
        return {t: {} for t in on}
    return {on: {}}


class WorkflowsExist(unittest.TestCase):
    def test_single_package_workflows_present(self):
        self.assertTrue(CI_PATH.exists(), "ci-partsiq.yml must be committed")
        self.assertTrue(DEPLOY_PATH.exists(), "deploy-partsiq.yml must be committed")

    def test_does_not_clobber_legacy_workflows(self):
        # The multi-service workflows from the earlier build must still be present.
        self.assertTrue((WORKFLOWS / "ci.yml").exists())
        self.assertTrue((WORKFLOWS / "deploy-backend.yml").exists())


class ActionsArePinned(unittest.TestCase):
    def test_all_actions_pinned_to_40_hex_sha(self):
        for path in (CI_PATH, DEPLOY_PATH):
            wf = _load(path)
            uses = _uses_values(wf)
            self.assertTrue(uses, f"{path.name}: expected at least one `uses:` action")
            for ref in uses:
                if ref.startswith("./"):
                    continue  # a local composite action is not SHA-pinnable
                self.assertRegex(
                    ref,
                    _SHA_PINNED,
                    f"{path.name}: action '{ref}' is not pinned to a 40-hex commit SHA",
                )


class LeastPrivilegePermissions(unittest.TestCase):
    def test_top_level_permissions_contents_read(self):
        for path in (CI_PATH, DEPLOY_PATH):
            wf = _load(path)
            perms = wf.get("permissions")
            self.assertIsInstance(perms, dict, f"{path.name}: missing top-level permissions")
            self.assertEqual(
                perms.get("contents"),
                "read",
                f"{path.name}: top-level contents permission must be read",
            )


class CiPipeline(unittest.TestCase):
    def setUp(self):
        self.wf = _load(CI_PATH)
        self.jobs = self.wf.get("jobs", {})
        self.text = yaml.dump(self.wf)

    def test_app_env_is_test(self):
        self.assertEqual(self.wf.get("env", {}).get("APP_ENV"), "test")

    def test_runs_service_isolated_api_suite_with_uv_all_packages(self):
        self.assertIn("uv run --all-packages pytest apps/api/tests", self.text)

    def test_runs_ruff(self):
        self.assertIn("ruff check apps/api", self.text)

    def test_runs_frontend_lint_typecheck_vitest(self):
        self.assertIn("pnpm --dir apps/web lint", self.text)
        self.assertIn("tsc --noEmit", self.text)
        self.assertIn("pnpm --dir apps/web test", self.text)

    def test_runs_deterministic_evaluations(self):
        # The deterministic evaluation harness runs offline (AI_MODE=fixture) against the
        # committed labelled cases; the prompt-21 suite reproduces every label and the pinned
        # dataset hash without any live provider call.
        self.assertIn("test_21_evaluation.py", self.text)
        self.assertIn("AI_MODE: fixture", self.text)

    def test_ci_may_run_on_pull_request(self):
        # CI (unlike deploy) is allowed and expected to gate pull requests.
        self.assertIn("pull_request", _triggers(self.wf))


class DeployGating(unittest.TestCase):
    def setUp(self):
        self.wf = _load(DEPLOY_PATH)
        self.jobs = self.wf.get("jobs", {})
        self.text = yaml.dump(self.wf)

    def test_workflow_dispatch_only_never_pull_request(self):
        triggers = _triggers(self.wf)
        self.assertIn("workflow_dispatch", triggers)
        self.assertNotIn("pull_request", triggers)
        self.assertNotIn("pull_request_target", triggers)
        self.assertNotIn("push", triggers)

    def test_production_environment_gate(self):
        gated = [name for name, cfg in self.jobs.items() if cfg.get("environment") == "production"]
        self.assertIn("deploy", gated, "the activation job must require the production environment")

    def test_oidc_id_token_and_no_static_aws_keys(self):
        has_id_token = any(
            (cfg.get("permissions") or {}).get("id-token") == "write"
            for cfg in self.jobs.values()
        )
        self.assertTrue(has_id_token, "deploy must request OIDC id-token: write")
        # No static AWS credentials anywhere in the workflow.
        self.assertNotIn("AWS_ACCESS_KEY_ID", self.text)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", self.text)

    def test_migration_runs_before_activation(self):
        migrate = next((n for n in self.jobs if "migrat" in n.lower()), None)
        self.assertIsNotNone(migrate, "a migration job is required")
        deploy = self.jobs.get("deploy", {})
        self.assertIn(migrate, deploy.get("needs") or [], "activation must depend on migrate")

    def test_infra_ready_flag_gate(self):
        self.assertIn("INFRA_READY", self.text)
        self.assertIn("INFRA_READY", str(self.jobs.get("deploy", {}).get("if")))

    def test_single_image_built_and_pushed(self):
        self.assertIn("docker build", self.text)
        self.assertIn("docker push", self.text)
        self.assertIn("ghcr.io", self.text)


class CheckerCatchesViolations(unittest.TestCase):
    """The owned static checker must flag unpinned actions, missing permissions, a
    pull_request-triggered deploy, and a missing environment gate."""

    _BAD_DEPLOY = """
name: deploy-bad
on:
  pull_request:
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: ./deploy.sh
"""

    def test_committed_single_package_workflows_are_clean(self):
        # The repo as a whole (including ci-partsiq.yml / deploy-partsiq.yml) is compliant.
        self.assertEqual(check_ci_configuration(REPO_ROOT), [])

    def test_catches_bad_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            wf = Path(tmp) / ".github" / "workflows"
            wf.mkdir(parents=True)
            (wf / "deploy-bad.yml").write_text(self._BAD_DEPLOY, encoding="utf-8")
            violations = " ".join(check_ci_configuration(Path(tmp)))
        self.assertIn("40-hex commit SHA", violations)  # unpinned action
        self.assertIn("permissions", violations)        # missing top-level permissions
        self.assertIn("pull_request", violations)       # deploy on PR (fork secret risk)
        self.assertIn("environment", violations)        # no manual-approval gate


if __name__ == "__main__":
    unittest.main(verbosity=2)
