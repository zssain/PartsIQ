"""Acceptance tests for prompt 01 — shared contracts and clients.

Runs offline: OpenAI and the database are replaced by in-process fakes, so these are
deterministic unit checks of the audited AI path, the budget gate, redaction, audit
writing and transaction-local actor context. Live provider/database behaviour is
exercised by later integration prompts, not here.

Covers F49 (audit), F64 (latency/cost), F67 (traces).
"""
from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "libs" / "partsiq_common"))

from partsiq_common import audit, security_context  # noqa: E402
from partsiq_common.ai import budget as budget_mod  # noqa: E402
from partsiq_common.ai import client as client_mod  # noqa: E402
from partsiq_common.contracts import (  # noqa: E402
    AIRequest,
    ActorContext,
    AuditEvent,
    EnquiryCreate,
    IntakeResult,
    ItemInput,
)
from partsiq_common.errors import ERROR_CATALOG, PartsIQError, error_envelope, http_status_for  # noqa: E402
from partsiq_common.telemetry import Stage, Tracer, redact_payload  # noqa: E402

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)


def a_valid_intake_json() -> str:
    return IntakeResult(
        language="en",
        preferred_locale="en",
        urgency="normal",
        items=[
            ItemInput(
                description="oil filter",
                quantity=Decimal("2"),
                source_message_id=uuid4(),
                source_start=0,
                source_end=10,
            )
        ],
    ).model_dump_json()


# --------------------------------------------------------------------------- contracts
class ContractsValidation(unittest.TestCase):
    def test_roundtrip_and_strictness(self) -> None:
        body = EnquiryCreate(text="need a filter", locale="en", destination_warehouse_id=1)
        restored = EnquiryCreate.model_validate_json(body.model_dump_json())
        self.assertEqual(restored.destination_warehouse_id, 1)

    def test_extra_fields_rejected(self) -> None:
        with self.assertRaises(Exception):
            EnquiryCreate.model_validate(
                {"text": "x", "locale": "en", "destination_warehouse_id": 1, "sneaky": True}
            )

    def test_field_bounds_enforced(self) -> None:
        with self.assertRaises(Exception):
            EnquiryCreate(text="", locale="en", destination_warehouse_id=1)


# --------------------------------------------------------------------------- errors
class ErrorsEnvelope(unittest.TestCase):
    def test_envelope_shape(self) -> None:
        env = error_envelope("STALE_REVISION", "req-1")
        self.assertEqual(set(env["error"]), {"code", "message", "request_id"})
        self.assertEqual(env["error"]["code"], "STALE_REVISION")
        self.assertEqual(env["error"]["request_id"], "req-1")

    def test_status_mapping_and_unknown_default(self) -> None:
        self.assertEqual(http_status_for("STALE_REVISION"), 409)
        self.assertEqual(http_status_for("VALIDATION_FAILED"), 422)
        self.assertEqual(http_status_for("not-a-code"), ERROR_CATALOG["DEPENDENCY_UNAVAILABLE"][0])

    def test_error_carries_no_internal_detail_to_client(self) -> None:
        err = PartsIQError("FORBIDDEN", internal_detail="user 42 lacks role on enquiry 99")
        env = error_envelope(err.code, "req-2", err.message)
        self.assertNotIn("42", json.dumps(env))
        self.assertNotIn("99", json.dumps(env))


# --------------------------------------------------------------------------- budget (F64)
class BudgetGate(unittest.TestCase):
    def _policy(self, **over) -> budget_mod.AllowancePolicy:
        base = dict(
            enabled=True,
            free_credit_usd=Decimal("1.00"),
            expires_at=NOW + timedelta(days=1),
            paid_budget_usd=Decimal("0"),
            daily_allowance_usd=Decimal("1.00"),
            session_allowance_usd=Decimal("0.50"),
        )
        base.update(over)
        return budget_mod.AllowancePolicy(**base)

    def test_unknown_model_price_blocks(self) -> None:
        with self.assertRaises(budget_mod.BudgetError):
            budget_mod.estimate_cost_usd("mystery-model", 100, 100)

    def test_known_model_price(self) -> None:
        cost = budget_mod.estimate_cost_usd("gpt-4.1-mini-2025-04-14", 1_000_000, 0)
        self.assertEqual(cost, Decimal("0.40"))

    def test_disabled_blocks_even_with_key(self) -> None:
        # A valid API key never implies free credit; only configuration enables calls.
        with self.assertRaises(budget_mod.BudgetError):
            self._policy(enabled=False).assert_callable(NOW)

    def test_paid_budget_nonzero_blocks(self) -> None:
        with self.assertRaises(budget_mod.BudgetError):
            self._policy(paid_budget_usd=Decimal("5")).assert_callable(NOW)

    def test_expired_credit_blocks(self) -> None:
        with self.assertRaises(budget_mod.BudgetError):
            self._policy(expires_at=NOW - timedelta(seconds=1)).assert_callable(NOW)

    def test_concurrent_reservations_cannot_exceed_cap(self) -> None:
        ledger = budget_mod.InMemoryBudgetLedger(self._policy())
        ledger.reserve("acct", Decimal("0.90"), NOW)
        with self.assertRaises(budget_mod.BudgetError):
            ledger.reserve("acct", Decimal("0.20"), NOW)  # would exceed free credit

    def test_session_cap_enforced(self) -> None:
        ledger = budget_mod.InMemoryBudgetLedger(self._policy())
        ledger.reserve("acct", Decimal("0.40"), NOW, session_id="s1")
        with self.assertRaises(budget_mod.BudgetError):
            ledger.reserve("acct", Decimal("0.20"), NOW, session_id="s1")  # > session cap 0.50

    def test_settle_and_snapshot(self) -> None:
        ledger = budget_mod.InMemoryBudgetLedger(self._policy())
        res = ledger.reserve("acct", Decimal("0.30"), NOW)
        ledger.settle(res, Decimal("0.10"), NOW)
        snap = ledger.snapshot()
        self.assertEqual(Decimal(snap["consumed_usd"]), Decimal("0.10"))
        self.assertEqual(Decimal(snap["reserved_usd"]), Decimal("0"))


# --------------------------------------------------------------------------- telemetry (F67)
class TelemetryRedaction(unittest.TestCase):
    def test_secrets_and_binary_redacted(self) -> None:
        safe = redact_payload(
            {"openai_api_key": "sk-123", "image_base64": "A" * 5000, "count": 3, "ok": True, "none": None}
        )
        self.assertEqual(safe["openai_api_key"], "[redacted]")
        self.assertTrue(safe["image_base64"].startswith("<bytes:"))
        self.assertEqual(safe["count"], 3)
        self.assertIs(safe["ok"], True)
        self.assertIsNone(safe["none"])

    def test_stage_measures_without_raising(self) -> None:
        with Stage("intake") as stage:
            pass
        self.assertGreaterEqual(stage.duration_ms, 0.0)
        self.assertEqual(stage.status, "ok")

    def test_tracer_disabled_is_noop(self) -> None:
        Tracer(enabled=False).emit("x", {"a": 1})  # must not raise

    def test_tracer_exporter_outage_is_swallowed(self) -> None:
        class Boom:
            def event(self, **kwargs):
                raise RuntimeError("exporter down")

        Tracer(enabled=True, _exporter=Boom()).emit("x", {"a": 1})  # must not raise


# --------------------------------------------------------------------------- audit (F49) / security ctx
class FakeCursor:
    def __init__(self, conn: "FakeConn") -> None:
        self.conn = conn

    async def __aenter__(self) -> "FakeCursor":
        return self

    async def __aexit__(self, *a) -> bool:
        return False

    async def execute(self, sql: str, params) -> None:
        self.conn.executed.append((sql, params))
        if self.conn.fail:
            raise RuntimeError("db down")

    async def fetchone(self):
        return (self.conn.next_id,)


class FakeConn:
    def __init__(self, next_id: int = 7, fail: bool = False) -> None:
        self.executed: list = []
        self.next_id = next_id
        self.fail = fail

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)


class AuditAppend(unittest.IsolatedAsyncioTestCase):
    def _event(self) -> AuditEvent:
        return AuditEvent(
            actor_type="user",
            actor_id="user-1",
            action="approve",
            entity_type="enquiry",
            entity_id="enq-1",
            request_id=uuid4(),
            enquiry_id=uuid4(),
            revision=3,
            payload={"api_key": "sk-secret", "count": 2},
        )

    async def test_append_returns_id_and_redacts_payload(self) -> None:
        conn = FakeConn(next_id=42)
        new_id = await audit.append_audit(conn, self._event())
        self.assertEqual(new_id, 42)
        _, params = conn.executed[-1]
        stored = json.loads(params[-1])
        self.assertEqual(stored["api_key"], "[redacted]")
        self.assertEqual(stored["count"], 2)

    async def test_audit_failure_propagates_for_rollback(self) -> None:
        with self.assertRaises(RuntimeError):
            await audit.append_audit(FakeConn(fail=True), self._event())


class FakeTxn:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class SecConn:
    def __init__(self) -> None:
        self.executed: list = []

    async def execute(self, sql: str, params=None) -> None:
        self.executed.append((sql, params))

    def transaction(self):
        return FakeTxn()


class SecConnCtx:
    def __init__(self, conn: SecConn) -> None:
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *a):
        return False


class FakePool:
    def __init__(self, conn: SecConn) -> None:
        self.conn = conn

    def connection(self):
        return SecConnCtx(self.conn)


class SecurityContext(unittest.IsolatedAsyncioTestCase):
    def _actor(self) -> ActorContext:
        return ActorContext(user_id=uuid4(), request_id=uuid4(), roles=["reviewer"])

    async def test_sets_transaction_local_actor_id(self) -> None:
        conn = SecConn()
        actor = self._actor()
        async with security_context.actor_transaction(actor, pool=FakePool(conn)) as yielded:
            self.assertIs(yielded, conn)
        statements = [sql for sql, _ in conn.executed]
        self.assertTrue(any("app.actor_id" in s and ", true)" in s for s in statements))
        actor_params = [p for s, p in conn.executed if "app.actor_id" in s][0]
        self.assertEqual(actor_params, (str(actor.user_id),))

    async def test_unconfigured_pool_raises(self) -> None:
        security_context.configure_actor_pool(None)
        with self.assertRaises(RuntimeError):
            async with security_context.actor_transaction(self._actor()):
                pass


# --------------------------------------------------------------------------- ai client (F64)
class FakeCompletions:
    def __init__(self, outcomes: list) -> None:
        self.outcomes = outcomes
        self.calls = 0
        self.last_kwargs: dict = {}

    async def create(self, **kwargs):
        self.last_kwargs = kwargs
        outcome = self.outcomes[min(self.calls, len(self.outcomes) - 1)]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeOpenAI:
    def __init__(self, outcomes: list) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions(outcomes))


def _response(content: str, prompt_tokens: int = 11, completion_tokens: int = 7):
    return SimpleNamespace(
        id="resp-123",
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


def an_ai_request() -> AIRequest:
    return AIRequest(
        request_key=uuid4(),
        enquiry_id=uuid4(),
        stage="intake",
        model="gpt-4.1-mini-2025-04-14",
        trusted_instructions="Extract items.",
        untrusted_text="I need 2 oil filters",
        output_schema_name="IntakeResult",
        max_output_tokens=512,
    )


class AIClientWrapper(unittest.IsolatedAsyncioTestCase):
    def _reservation(self):
        return budget_mod.BudgetReservation(id=uuid4(), account_id="acct", reserved_usd=Decimal("0.01"))

    async def test_success_returns_validated_result(self) -> None:
        fake = FakeOpenAI([_response(a_valid_intake_json())])
        result = await client_mod.call_structured(an_ai_request(), self._reservation(), client=fake)
        self.assertEqual(result.provider_request_id, "resp-123")
        self.assertEqual(result.input_tokens, 11)
        self.assertEqual(result.output_tokens, 7)
        # output-token cap and structured format were passed to the SDK
        self.assertEqual(fake.chat.completions.last_kwargs["max_tokens"], 512)
        self.assertEqual(fake.chat.completions.last_kwargs["response_format"]["type"], "json_schema")

    async def test_wrapper_makes_at_most_two_attempts(self) -> None:
        fake = FakeOpenAI([RuntimeError("boom"), RuntimeError("boom"), RuntimeError("boom")])
        with self.assertRaises(PartsIQError):
            await client_mod.call_structured(an_ai_request(), self._reservation(), client=fake)
        self.assertEqual(fake.chat.completions.calls, client_mod.MAX_ATTEMPTS)

    async def test_malformed_output_is_rejected(self) -> None:
        fake = FakeOpenAI([_response('{"not":"an intake result"}')])
        with self.assertRaises(PartsIQError):
            await client_mod.call_structured(an_ai_request(), self._reservation(), client=fake)

    async def test_messages_separate_trusted_and_untrusted(self) -> None:
        messages = client_mod._build_messages(an_ai_request())
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[0]["content"], "Extract items.")
        self.assertEqual(messages[1]["role"], "user")


class AIClientConstruction(unittest.TestCase):
    def test_sdk_retries_disabled(self) -> None:
        client = client_mod.build_openai_client(api_key="test-key-not-used")
        self.assertEqual(client.max_retries, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
