"""Acceptance tests for prompt 26 — AWS free-plan deployment (foundation gate).

preflight allows deployment only for a free plan with unexpired credit on an instance that
fits the MEASURED peak with headroom; it blocks otherwise with reasons. The bootstrap/deploy/
rollback scripts validate their inputs up front (a bad release SHA or an unprotected env file
is refused before any host action). Host provisioning/activation itself is BLOCKED offline.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "partsiq_common"))

from partsiq_common.contracts import AccountReceipt, SizingReceipt  # noqa: E402

EC2 = REPO_ROOT / "infra" / "ec2"


def _preflight():
    spec = importlib.util.spec_from_file_location("ec2_preflight", EC2 / "preflight.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_pf = _preflight()
NOW = datetime(2026, 10, 17, tzinfo=UTC)


def _account(credit="50", expires=None):
    return AccountReceipt(account_id="acct", plan="free", region="ap-south-1",
                          credit_usd=Decimal(credit), expires_at=expires or (NOW + timedelta(days=30)))


def _sizing(peak=2800, instance=4096, itype="t3.medium"):
    return SizingReceipt(instance_type=itype, peak_memory_mib=peak, instance_memory_mib=instance, measured_at=NOW)


class Preflight(unittest.TestCase):
    def test_allowed_when_free_credited_and_fits(self):
        decision = _pf.preflight(_account(), _sizing(), now=NOW)
        self.assertTrue(decision.allowed, decision.reasons)

    def test_blocked_without_credit(self):
        decision = _pf.preflight(_account(credit="0"), _sizing(), now=NOW)
        self.assertFalse(decision.allowed)
        self.assertTrue(any("credit" in r for r in decision.reasons))

    def test_blocked_when_expired(self):
        decision = _pf.preflight(_account(expires=NOW - timedelta(days=1)), _sizing(), now=NOW)
        self.assertFalse(decision.allowed)
        self.assertTrue(any("expired" in r for r in decision.reasons))

    def test_blocked_when_peak_exceeds_instance(self):  # free micro not assumed adequate
        decision = _pf.preflight(_account(), _sizing(peak=1200, instance=1024, itype="t3.micro"), now=NOW)
        self.assertFalse(decision.allowed)
        self.assertTrue(any("exceeds instance memory" in r for r in decision.reasons))

    def test_blocked_without_headroom(self):
        decision = _pf.preflight(_account(), _sizing(peak=2000, instance=2048), now=NOW)
        self.assertFalse(decision.allowed)
        self.assertTrue(any("headroom" in r for r in decision.reasons))


class Scripts(unittest.TestCase):
    def _run(self, script, *args):
        return subprocess.run(["bash", str(EC2 / script), *args], capture_output=True, text=True)

    def test_deploy_rejects_non_hex_sha(self):
        self.assertEqual(self._run("deploy.sh", "ZZZZ").returncode, 2)

    def test_deploy_accepts_hex_sha(self):
        self.assertEqual(self._run("deploy.sh", "a1b2c3d").returncode, 0)

    def test_rollback_rejects_non_hex_sha(self):
        self.assertEqual(self._run("rollback.sh", "nothex!").returncode, 2)

    def test_bootstrap_requires_env_path(self):
        self.assertEqual(self._run("bootstrap.sh").returncode, 2)
        self.assertEqual(self._run("bootstrap.sh", "/no/such/file.env").returncode, 2)

    def test_bootstrap_refuses_world_readable_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / "x.env"
            env.write_text("SECRET=${VAR}\n", encoding="utf-8")
            os.chmod(env, 0o644)
            self.assertEqual(self._run("bootstrap.sh", str(env)).returncode, 3)
            os.chmod(env, 0o600)
            self.assertEqual(self._run("bootstrap.sh", str(env)).returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
