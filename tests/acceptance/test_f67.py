"""F67 Traces — propagate ids, redact payloads, operate when tracing is unavailable.

No raw key or full photo is ever emitted; an exporter outage never breaks the call; budget
accounting stays local and authoritative regardless of tracing.
"""
from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "libs" / "partsiq_common"))

from partsiq_common.ai.budget import AllowancePolicy, InMemoryBudgetLedger, reserve_for_request  # noqa: E402
from partsiq_common.ai.client import call_structured  # noqa: E402
from partsiq_common.contracts import AIRequest, BudgetReservation, ReplySlots  # noqa: E402
from partsiq_common.telemetry import Tracer, build_tracer, redact_payload  # noqa: E402

FUTURE = datetime(2027, 1, 1, tzinfo=UTC)
NOW = datetime(2026, 10, 17, tzinfo=UTC)


class Capture:
    def __init__(self):
        self.events = []

    def event(self, *, name, **fields):
        self.events.append((name, fields))


class FakeOpenAI:
    def __init__(self, content):
        async def create(**kwargs):
            return SimpleNamespace(id="resp", choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                                   usage=SimpleNamespace(prompt_tokens=7, completion_tokens=3))

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


class Traces(unittest.IsolatedAsyncioTestCase):
    def test_redaction_strips_secrets_and_bytes(self):
        safe = redact_payload({"authorization": "Bearer x", "image_base64": "A" * 5000, "stage": "nameplate"})
        self.assertEqual(safe["authorization"], "[redacted]")
        self.assertTrue(str(safe["image_base64"]).startswith("<bytes:"))
        self.assertEqual(safe["stage"], "nameplate")

    def test_exporter_outage_never_raises(self):
        class Boom:
            def event(self, **_):
                raise RuntimeError("down")

        build_tracer(enabled=True, exporter=Boom()).emit("ai.call", {"stage": "reply"}, request_id="r1")  # no raise

    def test_disabled_tracer_is_noop(self):
        Tracer(enabled=False).emit("x", {"a": 1})

    async def test_call_emits_redacted_span_with_ids(self):
        capture = Capture()
        tracer = build_tracer(enabled=True, exporter=capture)
        enquiry_id = uuid4()
        request = AIRequest(
            request_key=uuid4(), enquiry_id=enquiry_id, stage="reply", model="gpt-4.1-mini-2025-04-14",
            trusted_instructions="t", untrusted_text="u", output_schema_name="ReplySlots", max_output_tokens=256,
        )
        budget = BudgetReservation(id=uuid4(), account_id="a", reserved_usd=Decimal("0.01"))
        slots = ReplySlots(greeting="Hi", explanation="ok", closing="bye").model_dump_json()
        await call_structured(request, budget, client=FakeOpenAI(slots), tracer=tracer)
        self.assertEqual(len(capture.events), 1)
        name, fields = capture.events[0]
        self.assertEqual(name, "ai.call")
        self.assertEqual(fields["request_id"], str(request.request_key))   # id propagated
        self.assertEqual(fields["enquiry_id"], str(enquiry_id))
        self.assertEqual(fields["status"], "ok")

    async def test_tracing_does_not_touch_budget_accounting(self):
        ledger = InMemoryBudgetLedger(policy=AllowancePolicy(
            enabled=True, free_credit_usd=Decimal("1"), expires_at=FUTURE, paid_budget_usd=Decimal("0"),
            daily_allowance_usd=Decimal("1"), session_allowance_usd=Decimal("1")))
        reserve_for_request(ledger, model="gpt-4.1-mini-2025-04-14", max_input_tokens=10, max_output_tokens=10,
                            account_id="a", now=NOW)
        before = ledger.snapshot()

        class Boom:
            def event(self, **_):
                raise RuntimeError("down")

        build_tracer(enabled=True, exporter=Boom()).emit("ai.call", {"stage": "reply"}, request_id="r1")
        self.assertEqual(ledger.snapshot(), before)  # local accounting authoritative


if __name__ == "__main__":
    unittest.main(verbosity=2)
