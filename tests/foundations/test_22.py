"""Acceptance tests for prompt 22 — security and failure recovery gate (foundation gate).

The live scenarios (foreign sessions, reset races, expired JWT, upload bombs, Redis down,
worker crash, stale lease, API timeout, simultaneous approvals) require a disposable local
Supabase and are BLOCKED here — the integration/e2e suites skip rather than fake a pass. This
gate exercises the OFFLINE security invariants over existing entry points: the disposable-
environment guard refuses production, require_access denies foreign/forged/missing-context
access (F04/F54), the verification gate rejects an oversold plan, and no secret is present in
the web bundle. Modules are loaded by file path to avoid the cross-service ``app`` name clash.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "libs" / "partsiq_common"))

from partsiq_common.contracts import (  # noqa: E402
    AccessAction,
    ActorContext,
    Allocation,
    CandidateEvidence,
    StockEvidence,
    TestConfig,
    VerificationEvidence,
    VerifiedFacts,
    VerifiedItem,
)
from partsiq_common.errors import PartsIQError  # noqa: E402

WEB = REPO_ROOT / "apps" / "web"
WHEN = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_sec = _load(REPO_ROOT / "tests" / "integration" / "test_security_recovery.py", "sec_recovery")
_perm = _load(REPO_ROOT / "services" / "gateway" / "app" / "permissions.py", "gw_permissions")
_ver = _load(REPO_ROOT / "services" / "orchestrator" / "app" / "verification.py", "orch_verification")


class DisposableGuard(unittest.TestCase):
    def test_local_and_test_allowed(self):
        _sec.assert_disposable_environment(TestConfig(app_env="test", database_url="postgres://localhost/pq", production_project_ref="prodref"))

    def test_production_dsn_refused(self):
        cfg = TestConfig(app_env="test", database_url="postgres://db.prodref.supabase.co/pq", production_project_ref="prodref")
        with self.assertRaises(PartsIQError):
            _sec.assert_disposable_environment(cfg)


class AccessControl(unittest.IsolatedAsyncioTestCase):
    def _repo(self, record):
        async def fetch(_id):
            return record
        return fetch

    async def test_foreign_demo_denied(self):  # F04
        rec = _perm.EnquiryAccess(enquiry_id=uuid4(), owner_id=uuid4(), session_id=uuid4(), session_generation=1, assigned_to=None)
        actor = ActorContext(user_id=uuid4(), request_id=uuid4(), roles=[], session_id=uuid4(), session_generation=1)
        with self.assertRaises(PartsIQError) as ctx:
            await _perm.require_access(actor, rec.enquiry_id, AccessAction.READ, repo=self._repo(rec))
        self.assertEqual(ctx.exception.http_status, 404)

    async def test_forged_role_denied(self):  # F54
        rec = _perm.EnquiryAccess(enquiry_id=uuid4(), owner_id=uuid4(), session_id=None, session_generation=None, assigned_to=uuid4())
        actor = ActorContext(user_id=uuid4(), request_id=uuid4(), roles=["reviewer"])
        with self.assertRaises(PartsIQError):
            await _perm.require_access(actor, rec.enquiry_id, AccessAction.REVIEW, repo=self._repo(rec))

    async def test_missing_context_denied(self):
        actor = ActorContext(user_id=uuid4(), request_id=uuid4(), roles=["reviewer"])
        with self.assertRaises(PartsIQError):
            await _perm.require_access(actor, uuid4(), AccessAction.REVIEW, repo=self._repo(None))


class VerificationGateSecurity(unittest.TestCase):
    def test_oversold_plan_is_rejected(self):
        item_id = uuid4()
        facts = VerifiedFacts(
            enquiry_id=uuid4(), revision=1, catalogue_version_id=(cv := uuid4()),
            items=[VerifiedItem(
                item_id=item_id, configuration_id=100, part_id=10, part_number="VP-FF-10",
                name_en="f", name_ar="ف", requested_quantity=Decimal("9"),
                allocations=[Allocation(warehouse_id=1, quantity=Decimal("9"), transfer_days=2, stock_updated_at=WHEN)],
                shortage=Decimal("0"), source_reference="SYNTH-CA-PB-CA-110 rev 1, section FILTERS", evidence_id=uuid4(),
            )],
        )
        evidence = VerificationEvidence(
            current_revision=1, active_catalogue_version_id=cv,
            candidates=[CandidateEvidence(item_id=item_id, part_id=10, configuration_id=100,
                                          evidence_id=facts.items[0].evidence_id, source_reference=facts.items[0].source_reference)],
            stock=[StockEvidence(part_id=10, warehouse_id=1, available=Decimal("5"), updated_at=WHEN)],  # only 5 < 9
        )
        self.assertFalse(_ver.verify_facts(facts, evidence).passed)


class NoSecretInBundle(unittest.TestCase):
    def test_no_secret_in_web_source(self):
        banned = ("SERVICE_ROLE", "SUPABASE_JWT", "SUPABASE_STORAGE_KEY", "INTERNAL_SERVICE_TOKEN", "OPENAI_API_KEY")
        for path in WEB.rglob("*.ts*"):
            if "node_modules" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            for secret in banned:
                self.assertNotIn(secret, text, f"{secret} in {path.relative_to(WEB)}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
