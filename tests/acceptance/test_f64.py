"""F64 Latency and AI cost — monotonic stage timing; worst-case credit reserved per attempt.

An unknown price or expired credit blocks the call; concurrent reservations cannot exceed the
cap; a valid API key never implies free credit; consumed/reserved allowance is exposed.
"""
from __future__ import annotations

import sys
import time
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
from partsiq_common.telemetry import Stage  # noqa: E402

FUTURE = datetime(2027, 1, 1, tzinfo=UTC)
NOW = datetime(2026, 10, 17, tzinfo=UTC)
MODEL = "gpt-4.1-mini-2025-04-14"


def _policy(**over):
    base = dict(enabled=True, free_credit_usd=Decimal("1"), expires_at=FUTURE, paid_budget_usd=Decimal("0"),
                daily_allowance_usd=Decimal("1"), session_allowance_usd=Decimal("1"))
    base.update(over)
    return AllowancePolicy(**base)


def _reserve(ledger):
    return reserve_for_request(ledger, model=MODEL, max_input_tokens=1000, max_output_tokens=500, account_id="a", now=NOW)


class LatencyAndCost(unittest.TestCase):
    def test_stage_timing_is_monotonic(self):
        with Stage("identify") as stage:
            time.sleep(0.001)
        self.assertGreater(stage.duration_ms, 0.0)

    def test_worst_case_reservation_exposed(self):
        ledger = InMemoryBudgetLedger(policy=_policy())
        _reserve(ledger)
        snap = ledger.snapshot()
        self.assertNotEqual(snap["reserved_usd"], "0")
        self.assertEqual(snap["free_credit_usd"], "1")

    def test_unknown_price_blocks(self):
        with self.assertRaises(BudgetError):
            reserve_for_request(InMemoryBudgetLedger(policy=_policy()), model="nope",
                                max_input_tokens=1, max_output_tokens=1, account_id="a", now=NOW)

    def test_expired_credit_blocks(self):
        ledger = InMemoryBudgetLedger(policy=_policy(expires_at=NOW - timedelta(days=1)))
        with self.assertRaises(BudgetError):
            _reserve(ledger)

    def test_key_does_not_imply_credit(self):
        ledger = InMemoryBudgetLedger(policy=_policy(enabled=False))
        with self.assertRaises(BudgetError):
            _reserve(ledger)

    def test_concurrent_reservations_cannot_exceed_cap(self):
        ledger = InMemoryBudgetLedger(policy=_policy(free_credit_usd=Decimal("0.0024")))
        _reserve(ledger)
        _reserve(ledger)
        with self.assertRaises(BudgetError):
            _reserve(ledger)


if __name__ == "__main__":
    unittest.main(verbosity=2)
