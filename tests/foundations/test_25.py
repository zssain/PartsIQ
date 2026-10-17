"""Acceptance tests for prompt 25 — CI and controlled deployment (foundation gate).

check_ci_configuration statically validates the committed workflows (SHA-pinned actions,
least-privilege permissions, OIDC + environment-gated deploy disabled until INFRA_READY,
migration before activation, never triggered by pull_request) and catches each violation in a
crafted bad config. No CI run is needed.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tools.ci_checks import check_ci_configuration  # noqa: E402

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


class CiConfiguration(unittest.TestCase):
    def test_committed_workflows_are_clean(self):
        self.assertEqual(check_ci_configuration(REPO_ROOT), [])

    def test_catches_violations(self):
        with tempfile.TemporaryDirectory() as tmp:
            wf = Path(tmp) / ".github" / "workflows"
            wf.mkdir(parents=True)
            (wf / "deploy-bad.yml").write_text(_BAD_DEPLOY, encoding="utf-8")
            violations = " ".join(check_ci_configuration(Path(tmp)))
        self.assertIn("40-hex commit SHA", violations)       # unpinned action
        self.assertIn("permissions", violations)             # missing permissions
        self.assertIn("pull_request", violations)            # deploy on PR (fork secret risk)
        self.assertIn("environment", violations)             # no approval gate

    def test_deploy_disabled_until_infra_ready(self):
        import yaml

        deploy = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "deploy-backend.yml").read_text(encoding="utf-8"))
        self.assertIn("INFRA_READY", str(deploy["jobs"]["deploy"].get("if")))
        triggers = deploy.get("on") or deploy.get(True)  # PyYAML parses 'on:' as True
        self.assertNotIn("pull_request", triggers)
        self.assertNotIn("pull_request_target", triggers)


if __name__ == "__main__":
    unittest.main(verbosity=2)
