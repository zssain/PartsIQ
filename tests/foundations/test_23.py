"""Acceptance tests for prompt 23 — observability and credit limits (foundation gate).

Local accounting is authoritative: a manually-confirmed allowance (amount + future expiry +
zero paid budget) is required, an unknown price or expired credit blocks, worst-case cost is
reserved atomically per attempt, and a tracing outage never changes a decision. Metrics are
staff-only and exclude demos by default; readiness reports each subsystem (unconfigured =
False). Covers F64, F67.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "libs" / "partsiq_common"))

from partsiq_common.ai.budget import (  # noqa: E402
    AllowancePolicy,
    BudgetError,
    InMemoryBudgetLedger,
    reserve_for_request,
)
from partsiq_common.contracts import ActorContext, MetricsQuery  # noqa: E402
from partsiq_common.errors import PartsIQError  # noqa: E402
from partsiq_common.telemetry import Stage, Tracer, build_tracer  # noqa: E402
from tools.check_readiness import readiness_report  # noqa: E402
from tools.credit_allowance import validate_allowance  # noqa: E402

FUTURE = datetime(2027, 1, 1, tzinfo=UTC)
NOW = datetime(2026, 10, 17, tzinfo=UTC)


def _metrics_module():
    path = REPO_ROOT / "services" / "gateway" / "app" / "metrics.py"
    spec = importlib.util.spec_from_file_location("gw_metrics", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_metrics = _metrics_module()


def _policy(**over):
    base = dict(enabled=True, free_credit_usd=Decimal("1"), expires_at=FUTURE,
                paid_budget_usd=Decimal("0"), daily_allowance_usd=Decimal("1"), session_allowance_usd=Decimal("1"))
    base.update(over)
    return AllowancePolicy(**base)


class Allowance(unittest.TestCase):
    def test_valid_allowance(self):
        allowance = validate_allowance(Decimal("5"), FUTURE, Decimal("0"), now=NOW)
        self.assertEqual(allowance.paid_budget_usd, Decimal("0"))

    def test_paid_budget_blocks(self):
        with self.assertRaises(PartsIQError):
            validate_allowance(Decimal("5"), FUTURE, Decimal("1"), now=NOW)

    def test_expired_blocks(self):
        with self.assertRaises(PartsIQError):
            validate_allowance(Decimal("5"), NOW - timedelta(days=1), Decimal("0"), now=NOW)


class Reservation(unittest.TestCase):
    def test_worst_case_reserved_and_exposed(self):
        ledger = InMemoryBudgetLedger(policy=_policy())
        res = reserve_for_request(ledger, model="gpt-4.1-mini-2025-04-14", max_input_tokens=1000,
                                  max_output_tokens=500, account_id="a", now=NOW)
        self.assertGreater(res.reserved_usd, 0)
        self.assertNotEqual(ledger.snapshot()["reserved_usd"], "0")

    def test_unknown_price_blocks(self):
        with self.assertRaises(BudgetError):
            reserve_for_request(InMemoryBudgetLedger(policy=_policy()), model="unpriced-model",
                                max_input_tokens=10, max_output_tokens=10, account_id="a", now=NOW)

    def test_disabled_policy_blocks_even_with_key(self):  # API key never implies credit
        ledger = InMemoryBudgetLedger(policy=_policy(enabled=False))
        with self.assertRaises(BudgetError):
            reserve_for_request(ledger, model="gpt-4.1-mini-2025-04-14", max_input_tokens=10,
                                max_output_tokens=10, account_id="a", now=NOW)

    def test_cap_not_exceeded_by_many_reservations(self):
        ledger = InMemoryBudgetLedger(policy=_policy(free_credit_usd=Decimal("0.0024")))  # ~2 calls
        for _ in range(2):
            reserve_for_request(ledger, model="gpt-4.1-mini-2025-04-14", max_input_tokens=1000,
                                max_output_tokens=500, account_id="a", now=NOW)
        with self.assertRaises(BudgetError):
            reserve_for_request(ledger, model="gpt-4.1-mini-2025-04-14", max_input_tokens=1000,
                                max_output_tokens=500, account_id="a", now=NOW)


class Telemetry(unittest.TestCase):
    def test_stage_uses_monotonic_clock(self):
        with Stage("search") as stage:
            pass
        self.assertGreaterEqual(stage.duration_ms, 0.0)
        self.assertEqual(stage.status, "ok")

    def test_tracer_outage_is_safe_and_local_accounting_unchanged(self):
        class Boom:
            def event(self, **_):
                raise RuntimeError("exporter down")

        ledger = InMemoryBudgetLedger(policy=_policy())
        before = ledger.snapshot()
        tracer = build_tracer(enabled=True, exporter=Boom())
        tracer.emit("ai.call", {"authorization": "secret-token", "stage": "reply"}, request_id="r1")  # must not raise
        self.assertEqual(ledger.snapshot(), before)  # tracing cannot touch the budget

    def test_disabled_tracer_is_noop(self):
        Tracer(enabled=False).emit("x", {"a": 1})  # no exporter, no raise


class Metrics(unittest.IsolatedAsyncioTestCase):
    class FakeRepo:
        def __init__(self, samples):
            self._samples = samples
            self.query = None

        async def samples(self, query):
            self.query = query
            return self._samples

    async def test_staff_only(self):
        repo = self.FakeRepo(_metrics.MetricsSamples())
        actor = ActorContext(user_id=__import__("uuid").uuid4(), request_id=__import__("uuid").uuid4(), roles=[])
        with self.assertRaises(PartsIQError) as ctx:
            await _metrics.get_metrics(actor, MetricsQuery(start=NOW, end=FUTURE), repo=repo)
        self.assertEqual(ctx.exception.http_status, 403)

    async def test_computes_median_p95_and_excludes_demo_by_default(self):
        samples = _metrics.MetricsSamples(
            enquiry_count=10, approved_count=6, clarification_count=2, evaluated_count=5, correct_count=4,
            review_seconds=[10, 20, 30], latencies_ms=[100, 200, 300, 400, 500], estimated_cost_usd=Decimal("0.05"),
        )
        repo = self.FakeRepo(samples)
        import uuid
        actor = ActorContext(user_id=uuid.uuid4(), request_id=uuid.uuid4(), roles=["reviewer"])
        view = await _metrics.get_metrics(actor, MetricsQuery(start=NOW, end=FUTURE), repo=repo)
        self.assertEqual(view.median_review_seconds, 20)
        self.assertEqual(view.p95_latency_ms, 500)
        self.assertFalse(repo.query.include_demo)  # demos excluded by default


class Readiness(unittest.IsolatedAsyncioTestCase):
    async def test_default_all_false(self):
        report = await readiness_report()
        self.assertFalse(report.database)
        self.assertFalse(report.ai_credit_enabled)

    async def test_injected_probes_and_failing_probe(self):
        async def ok():
            return True

        async def boom():
            raise RuntimeError("unreachable")

        report = await readiness_report(probes={"database": ok, "redis": boom})
        self.assertTrue(report.database)
        self.assertFalse(report.redis)  # a failing probe is not-ready, never an error


if __name__ == "__main__":
    unittest.main(verbosity=2)
