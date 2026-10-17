"""Foundation 23 acceptance: structured logs, tracing, metrics and the Snowflake outbox.

Ports the behaviour characterized by the legacy F64/F67 acceptance tests onto the single
``partsiq`` package and adds the outbox/reporting coverage (F63). Fully deterministic and
offline: live Langfuse, the live metrics database and live Snowflake are BLOCKED. Each is an
injected fake; the live Snowflake path is SKIPPED (never faked as a warehouse), gated behind
``PARTSIQ_LIVE_INFRA``.

Covered behaviours:
  * Observability (F67): redaction strips secrets, JWTs, signed URLs and full photos; the
    tracer survives an exporter outage (never raises); a disabled tracer is a no-op; ids
    propagate; monotonic stage timing is positive and produces a typed TraceView.
  * Outbox (F63): events are redacted to the allowlist before storage; export is idempotent on
    EVENT_ID; rows are acknowledged ONLY after remote success; a remote failure leaves events
    pending (nothing lost); a crash after MERGE before ack safely repeats the same event.
  * Metrics (F63/F64): get_metrics is staff-only (a customer is refused); demos are excluded by
    default and included on request; median review, nearest-rank p95 and summed cost are
    computed correctly; an empty sample yields None not a fabricated zero.
  * Allowance (F64): validate_allowance blocks a non-zero paid budget, a non-positive amount
    and an expired allowance, and never infers an allowance from a key.
"""
from __future__ import annotations

import logging
import os
import time
import unittest
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from partsiq.analytics import outbox as outbox_mod
from partsiq.analytics import service as service_mod
from partsiq.analytics.outbox import (
    InMemoryOutboxStore,
    OutboxRow,
    append_event,
    event_cost,
    export_events,
    redact_event,
    sync_view,
)
from partsiq.analytics.service import (
    MetricsSamples,
    allowance_from_set,
    allowance_view,
    get_metrics,
    validate_allowance,
)
from partsiq.analytics.snowflake import SnowflakeReporter
from partsiq.core.api_models import AllowanceSet, AnalyticsSyncReceipt
from partsiq.core.contracts import ActorContext, CreditAllowance, MetricsQuery
from partsiq.core.errors import PartsIQError
from partsiq.core.observability import (
    LangfuseExporter,
    Stage,
    Tracer,
    build_trace_view,
    build_tracer,
    log_event,
    redact_payload,
)
from partsiq.core.settings import Settings

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
FUTURE = datetime(2027, 1, 1, tzinfo=UTC)
PAST = datetime(2025, 1, 1, tzinfo=UTC)


def _actor(roles: list[str]) -> ActorContext:
    return ActorContext(user_id=uuid4(), request_id=uuid4(), roles=roles)  # type: ignore[arg-type]


def _query(*, include_demo: bool = False) -> MetricsQuery:
    return MetricsQuery(start=NOW - timedelta(days=7), end=NOW, include_demo=include_demo)


class _FakeMetricsRepo:
    """Deterministic metrics repository; records whether include_demo was honoured."""

    def __init__(self, operational: MetricsSamples, demo_included: MetricsSamples) -> None:
        self._operational = operational
        self._demo_included = demo_included
        self.seen_include_demo: bool | None = None

    async def samples(self, actor: ActorContext, query: MetricsQuery) -> MetricsSamples:
        self.seen_include_demo = query.include_demo
        return self._demo_included if query.include_demo else self._operational


# --------------------------------------------------------------------------- observability (F67)


class Observability(unittest.TestCase):
    def test_redaction_strips_secrets_and_bytes(self):
        safe = redact_payload(
            {"authorization": "Bearer x", "image_base64": "A" * 5000, "stage": "nameplate"}
        )
        self.assertEqual(safe["authorization"], "[redacted]")
        self.assertTrue(str(safe["image_base64"]).startswith("<bytes:"))
        self.assertEqual(safe["stage"], "nameplate")

    def test_redaction_strips_jwt_and_signed_url(self):
        safe = redact_payload(
            {
                "jwt": "eyJhbGciOi.payload.sig",
                "download_url": "https://x.supabase.co/object/sign/a.pdf?token=abc&sig=zzz",
                "db_error": "ok text",
            }
        )
        self.assertEqual(safe["jwt"], "[redacted]")
        # A value that is itself a signed URL is dropped even though the key is innocuous.
        self.assertEqual(safe["download_url"], "[redacted-url]")
        self.assertEqual(safe["db_error"], "ok text")

    def test_disabled_tracer_is_noop(self):
        Tracer(enabled=False).emit("x", {"a": 1})  # no exporter, no raise

    def test_exporter_outage_never_raises(self):
        class Boom:
            def event(self, **_):
                raise RuntimeError("down")

        # An exporter outage must never break approval (F67): emit swallows it.
        build_tracer(enabled=True, exporter=Boom()).emit(
            "ai.call", {"stage": "reply"}, request_id="r1"
        )

    def test_emit_redacts_and_propagates_ids(self):
        class Capture:
            def __init__(self):
                self.events = []

            def event(self, *, name, **fields):
                self.events.append((name, fields))

        capture = Capture()
        enquiry_id = str(uuid4())
        build_tracer(enabled=True, exporter=capture).emit(
            "ai.call",
            {"authorization": "Bearer secret", "stage": "reply"},
            request_id="r1",
            enquiry_id=enquiry_id,
        )
        self.assertEqual(len(capture.events), 1)
        name, fields = capture.events[0]
        self.assertEqual(name, "ai.call")
        self.assertEqual(fields["request_id"], "r1")
        self.assertEqual(fields["enquiry_id"], enquiry_id)
        self.assertEqual(fields["authorization"], "[redacted]")  # secret never leaves

    def test_stage_timing_is_monotonic_and_typed(self):
        with Stage("identify") as stage:
            time.sleep(0.001)
        self.assertGreater(stage.duration_ms, 0.0)
        self.assertEqual(stage.status, "ok")
        trace_stage = stage.as_trace_stage()
        self.assertEqual(trace_stage.stage, "identify")
        self.assertEqual(trace_stage.status, "ok")
        self.assertIsNone(trace_stage.error_code)

    def test_stage_records_error_code_without_suppressing(self):
        with self.assertRaises(PartsIQError):
            with Stage("verify") as stage:
                raise PartsIQError("CONFLICT", internal_detail="boom")
        self.assertEqual(stage.status, "error")
        self.assertEqual(stage.error_code, "CONFLICT")

    def test_build_trace_view(self):
        with Stage("intake") as s1:
            time.sleep(0.0005)
        enquiry_id = uuid4()
        view = build_trace_view(enquiry_id, 2, [s1])
        self.assertEqual(view.enquiry_id, enquiry_id)
        self.assertEqual(view.revision, 2)
        self.assertEqual(len(view.stages), 1)
        self.assertEqual(view.stages[0].stage, "intake")

    def test_log_event_never_raises_and_redacts(self):
        records: list[logging.LogRecord] = []

        class _Handler(logging.Handler):
            def emit(self, record):
                records.append(record)

        logger = logging.getLogger("partsiq.observability")
        handler = _Handler()
        previous_level = logger.level
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        try:
            log_event(logging.INFO, "ai call", api_key="sk-secret", stage="reply")
        finally:
            logger.removeHandler(handler)
            logger.setLevel(previous_level)
        self.assertTrue(records)
        self.assertEqual(records[-1].fields["api_key"], "[redacted]")  # type: ignore[attr-defined]
        self.assertEqual(records[-1].fields["stage"], "reply")  # type: ignore[attr-defined]

    def test_langfuse_exporter_import_is_lazy(self):
        # Constructing the exporter must NOT import langfuse (optional [trace] extra). The
        # lazy import only fires on first event(); langfuse is absent here so it raises then.
        exporter = LangfuseExporter(public_key="p", secret_key="s", host="https://lf")
        with self.assertRaises(ImportError):
            exporter.event(name="x")


# --------------------------------------------------------------------------- outbox (F63)


class FakeSink:
    """A reporting sink that records every MERGE and can be toggled to fail."""

    def __init__(self, *, succeed: bool = True) -> None:
        self.succeed = succeed
        self.merged_batches: list[list[UUID]] = []

    def merge_events(self, rows: list[OutboxRow]) -> AnalyticsSyncReceipt:
        self.merged_batches.append([r.event_id for r in rows])
        return AnalyticsSyncReceipt(
            run_id=uuid4(),
            row_count=len(rows) if self.succeed else 0,
            query_id="qid" if self.succeed else None,
            succeeded=self.succeed,
        )


class Outbox(unittest.TestCase):
    def test_redact_event_keeps_only_allowlisted_fields(self):
        raw = {
            "event_type": "ai.call",
            "occurred_at": "2026-10-17T12:00:00Z",
            "is_demo": False,
            "status": "ok",
            "stage": "reply",
            "duration_ms": 12.5,
            "input_tokens": 7,
            "output_tokens": 3,
            "estimated_cost_usd": Decimal("0.0012"),
            # Everything below is forbidden in analytics and must be dropped.
            "customer_message": "my serial is 12345",
            "serial_text": "SN-0001",
            "note": "internal note",
            "authorization": "Bearer x",
            "image_base64": "A" * 100,
            "signed_url": "https://x?sig=y",
        }
        safe = redact_event(raw)
        self.assertEqual(
            set(safe),
            {
                "event_type",
                "occurred_at",
                "is_demo",
                "status",
                "stage",
                "duration_ms",
                "input_tokens",
                "output_tokens",
                "estimated_cost_usd",
            },
        )
        self.assertNotIn("customer_message", safe)
        self.assertNotIn("serial_text", safe)
        self.assertNotIn("note", safe)
        self.assertEqual(safe["estimated_cost_usd"], "0.0012")  # Decimal -> str, no precision loss
        self.assertEqual(event_cost(safe), Decimal("0.0012"))

    def test_append_stores_redacted_row(self):
        store = InMemoryOutboxStore()
        row = append_event(
            store,
            event_id=uuid4(),
            event_type="enquiry.approved",
            occurred_at=NOW,
            is_demo=False,
            event={"status": "approved", "serial_text": "SN-1", "api_key": "sk"},
        )
        self.assertNotIn("serial_text", row.payload)
        self.assertNotIn("api_key", row.payload)
        self.assertEqual(row.payload["status"], "approved")
        self.assertEqual(store.pending_count(), 1)

    def test_export_acks_only_after_remote_success(self):
        store = InMemoryOutboxStore()
        for _ in range(3):
            append_event(
                store,
                event_id=uuid4(),
                event_type="ai.call",
                occurred_at=NOW,
                is_demo=False,
                event={"status": "ok", "estimated_cost_usd": Decimal("0.001")},
            )
        sink = FakeSink(succeed=True)
        receipt = export_events(store, sink, batch_size=10, now=NOW)
        self.assertTrue(receipt.succeeded)
        self.assertEqual(receipt.row_count, 3)
        self.assertEqual(store.pending_count(), 0)  # all acknowledged after remote success
        self.assertEqual(store.last_success_at(), NOW)

    def test_remote_failure_does_not_lose_events(self):
        store = InMemoryOutboxStore()
        append_event(
            store,
            event_id=uuid4(),
            event_type="ai.call",
            occurred_at=NOW,
            is_demo=False,
            event={"status": "ok"},
        )
        sink = FakeSink(succeed=False)
        receipt = export_events(store, sink, batch_size=10, now=NOW)
        self.assertFalse(receipt.succeeded)
        # Nothing acknowledged: the durable row is still pending — Snowflake loss loses nothing.
        self.assertEqual(store.pending_count(), 1)
        self.assertIsNone(store.last_success_at())

    def test_export_is_idempotent_on_event_id(self):
        store = InMemoryOutboxStore()
        event_id = uuid4()
        # Appending the same business event twice (a retried mutation) yields ONE row.
        for _ in range(2):
            append_event(
                store,
                event_id=event_id,
                event_type="ai.call",
                occurred_at=NOW,
                is_demo=False,
                event={"status": "ok"},
            )
        self.assertEqual(store.pending_count(), 1)

        sink = FakeSink(succeed=True)
        # Simulate a crash AFTER the remote MERGE but BEFORE acknowledgement: the sink saw the
        # batch, yet the store never marked it delivered. Re-running re-ships the SAME event_id;
        # the remote MERGE dedupes on EVENT_ID so no duplicate is created.
        rows = store.pending(10)
        sink.merge_events(rows)  # remote write happened...
        # ...but the process crashed before ack; the row is still pending.
        self.assertEqual(store.pending_count(), 1)
        export_events(store, sink, batch_size=10, now=NOW)  # safe repeat
        self.assertEqual(sink.merged_batches, [[event_id], [event_id]])  # same id re-MERGEd
        self.assertEqual(store.pending_count(), 0)

    def test_export_empty_is_success_noop(self):
        store = InMemoryOutboxStore()
        sink = FakeSink(succeed=True)
        receipt = export_events(store, sink, now=NOW)
        self.assertTrue(receipt.succeeded)
        self.assertEqual(receipt.row_count, 0)
        self.assertEqual(sink.merged_batches, [])  # nothing shipped

    def test_sync_view_reports_pending_and_freshness(self):
        store = InMemoryOutboxStore()
        append_event(
            store,
            event_id=uuid4(),
            event_type="ai.call",
            occurred_at=NOW,
            is_demo=False,
            event={"status": "ok"},
        )
        view = sync_view(store, source="snowflake", stale=True)
        self.assertEqual(view.pending_events, 1)
        self.assertIsNone(view.last_success_at)
        self.assertEqual(view.source, "snowflake")
        self.assertTrue(view.stale)


# --------------------------------------------------------------------------- snowflake sink (F63)


class FakeCursor:
    """Records executed SQL + bound params; models an idempotent EVENT_ID MERGE in a dict."""

    sfqid = "sfqid-123"

    def __init__(self, table: dict[str, tuple], *, fail: bool = False) -> None:
        self._table = table
        self._fail = fail
        self.executed: list[tuple[str, object]] = []

    def execute(self, command: str, params: object | None = None):
        self.executed.append((command, params))
        if self._fail and command.strip().upper().startswith("MERGE"):
            raise RuntimeError("snowflake down")
        if command.strip().upper().startswith("MERGE") and params:
            event_id = params[0]  # type: ignore[index]
            self._table[event_id] = tuple(params)  # upsert — later write replaces, no duplicate
        return None

    def fetchall(self):
        return []

    def close(self):
        pass


class FakeConnection:
    def __init__(self, table: dict[str, tuple], *, fail: bool = False) -> None:
        self._table = table
        self._fail = fail
        self.committed = 0
        self.rolled_back = 0

    def cursor(self):
        return FakeCursor(self._table, fail=self._fail)

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1

    def close(self):
        pass


def _settings() -> Settings:
    return Settings(snowflake_database="PARTSIQ_DEV")


def _row(event_id: UUID) -> OutboxRow:
    return OutboxRow(
        event_id=event_id,
        event_type="ai.call",
        occurred_at=NOW,
        is_demo=False,
        payload={
            "status": "ok",
            "stage": "reply",
            "duration_ms": 10.0,
            "input_tokens": 7,
            "output_tokens": 3,
            "estimated_cost_usd": "0.0012",
        },
    )


class SnowflakeSink(unittest.TestCase):
    def test_merge_uses_bound_params_and_allowlisted_identifiers(self):
        table: dict[str, tuple] = {}
        # A cursor that captures the exact SQL + params so we can assert the identifiers and
        # that every event field is a BOUND parameter, not interpolated SQL.
        captured: list[tuple[str, object]] = []

        class CapturingCursor(FakeCursor):
            def execute(self, command, params=None):
                captured.append((command, params))
                return super().execute(command, params)

        class CapturingConnection(FakeConnection):
            def cursor(self):
                return CapturingCursor(self._table, fail=self._fail)

        conn = CapturingConnection(table)
        reporter = SnowflakeReporter(conn, _settings())
        event_id = uuid4()
        receipt = reporter.merge_events([_row(event_id)])
        self.assertTrue(receipt.succeeded)
        self.assertEqual(receipt.row_count, 1)
        self.assertEqual(receipt.query_id, "sfqid-123")
        self.assertEqual(conn.committed, 1)
        self.assertIn(str(event_id), table)
        merge_cmd = next(cmd for cmd, _ in captured if cmd.strip().upper().startswith("MERGE"))
        # Fixed allowlisted identifiers (DEV database + REPORTING.EVENTS), interpolated only from
        # validated Settings — never from an event field.
        self.assertIn("PARTSIQ_DEV.REPORTING.EVENTS", merge_cmd)
        self.assertIn("MERGE INTO", merge_cmd)
        self.assertIn("target.EVENT_ID = source.EVENT_ID", merge_cmd)  # idempotent on EVENT_ID
        # Only '?' placeholders carry data — no event field appears inline in the SQL text.
        self.assertNotIn("ai.call", merge_cmd)

    def test_merge_binds_values_not_sql(self):
        table: dict[str, tuple] = {}
        conn = FakeConnection(table)
        reporter = SnowflakeReporter(conn, _settings())
        reporter.merge_events([_row(uuid4())])
        # The stored tuple is a BOUND parameter list — the event fields are values, not SQL.
        (_event_id, stored) = next(iter(table.items()))
        self.assertEqual(stored[1], "ai.call")  # EVENT_TYPE bound as a value
        self.assertEqual(stored[-1], "0.0012")  # ESTIMATED_COST_USD bound as a value

    def test_merge_is_idempotent_on_event_id(self):
        table: dict[str, tuple] = {}
        conn = FakeConnection(table)
        reporter = SnowflakeReporter(conn, _settings())
        event_id = uuid4()
        reporter.merge_events([_row(event_id)])
        reporter.merge_events([_row(event_id)])  # same EVENT_ID again
        self.assertEqual(len(table), 1)  # upsert, not a duplicate row

    def test_remote_failure_reports_not_succeeded_and_rolls_back(self):
        table: dict[str, tuple] = {}
        conn = FakeConnection(table, fail=True)
        reporter = SnowflakeReporter(conn, _settings())
        receipt = reporter.merge_events([_row(uuid4())])
        self.assertFalse(receipt.succeeded)  # never an empty SUCCESS
        self.assertEqual(receipt.row_count, 0)
        self.assertEqual(conn.rolled_back, 1)
        self.assertEqual(conn.committed, 0)

    def test_outbox_export_through_snowflake_sink(self):
        # End-to-end: durable outbox -> SnowflakeReporter MERGE -> ack after success.
        store = InMemoryOutboxStore()
        append_event(
            store,
            event_id=uuid4(),
            event_type="ai.call",
            occurred_at=NOW,
            is_demo=False,
            event={"status": "ok", "estimated_cost_usd": Decimal("0.002")},
        )
        table: dict[str, tuple] = {}
        reporter = SnowflakeReporter(FakeConnection(table), _settings())
        receipt = export_events(store, reporter, now=NOW)
        self.assertTrue(receipt.succeeded)
        self.assertEqual(store.pending_count(), 0)
        self.assertEqual(len(table), 1)


# --------------------------------------------------------------------------- metrics (F63/F64)


class Metrics(unittest.IsolatedAsyncioTestCase):
    async def test_customer_is_refused(self):
        repo = _FakeMetricsRepo(MetricsSamples(), MetricsSamples())
        with self.assertRaises(PartsIQError) as ctx:
            await get_metrics(_actor(roles=[]), _query(), repo=repo)
        self.assertEqual(ctx.exception.code, "FORBIDDEN")
        self.assertIsNone(repo.seen_include_demo)  # repo never even queried

    async def test_staff_allowed(self):
        repo = _FakeMetricsRepo(
            MetricsSamples(enquiry_count=5, approved_count=3), MetricsSamples()
        )
        view = await get_metrics(_actor(roles=["reviewer"]), _query(), repo=repo)
        self.assertEqual(view.enquiry_count, 5)
        self.assertEqual(view.approved_count, 3)

    async def test_demos_excluded_by_default(self):
        operational = MetricsSamples(enquiry_count=2)
        demo_included = MetricsSamples(enquiry_count=99)
        repo = _FakeMetricsRepo(operational, demo_included)
        view = await get_metrics(_actor(roles=["admin"]), _query(), repo=repo)
        self.assertFalse(repo.seen_include_demo)
        self.assertEqual(view.enquiry_count, 2)  # demo traffic excluded

    async def test_demos_included_on_request(self):
        operational = MetricsSamples(enquiry_count=2)
        demo_included = MetricsSamples(enquiry_count=99)
        repo = _FakeMetricsRepo(operational, demo_included)
        view = await get_metrics(_actor(roles=["admin"]), _query(include_demo=True), repo=repo)
        self.assertTrue(repo.seen_include_demo)
        self.assertEqual(view.enquiry_count, 99)

    async def test_median_p95_and_summed_cost(self):
        samples = MetricsSamples(
            review_seconds=[10.0, 30.0, 20.0, 40.0],  # median of 4 -> (20+30)/2 = 25
            latencies_ms=[float(i) for i in range(1, 101)],  # p95 nearest-rank -> ceil(0.95*100)=95
            estimated_cost_usd=Decimal("0.1234"),
        )
        repo = _FakeMetricsRepo(samples, MetricsSamples())
        view = await get_metrics(_actor(roles=["reviewer"]), _query(), repo=repo)
        self.assertEqual(view.median_review_seconds, 25.0)
        self.assertEqual(view.p95_latency_ms, 95.0)
        self.assertEqual(view.estimated_cost_usd, Decimal("0.1234"))

    async def test_empty_samples_yield_none_not_zero(self):
        repo = _FakeMetricsRepo(MetricsSamples(), MetricsSamples())
        view = await get_metrics(_actor(roles=["reviewer"]), _query(), repo=repo)
        self.assertIsNone(view.median_review_seconds)  # no fabricated percentage/zero
        self.assertIsNone(view.p95_latency_ms)
        self.assertEqual(view.estimated_cost_usd, Decimal(0))

    async def test_p95_single_sample(self):
        repo = _FakeMetricsRepo(MetricsSamples(latencies_ms=[42.0]), MetricsSamples())
        view = await get_metrics(_actor(roles=["reviewer"]), _query(), repo=repo)
        self.assertEqual(view.p95_latency_ms, 42.0)


# --------------------------------------------------------------------------- allowance (F64)


class Allowance(unittest.TestCase):
    def test_valid_allowance(self):
        allowance = validate_allowance(Decimal("5"), FUTURE, Decimal("0"), now=NOW)
        self.assertEqual(allowance.amount_usd, Decimal("5"))
        self.assertEqual(allowance.paid_budget_usd, Decimal("0"))

    def test_non_zero_paid_budget_blocks(self):
        with self.assertRaises(PartsIQError) as ctx:
            validate_allowance(Decimal("5"), FUTURE, Decimal("1"), now=NOW)
        self.assertEqual(ctx.exception.code, "CREDIT_UNAVAILABLE")

    def test_non_positive_amount_blocks(self):
        with self.assertRaises(PartsIQError):
            validate_allowance(Decimal("0"), FUTURE, Decimal("0"), now=NOW)

    def test_expired_allowance_blocks(self):
        with self.assertRaises(PartsIQError):
            validate_allowance(Decimal("5"), PAST, Decimal("0"), now=NOW)

    def test_allowance_never_inferred_from_a_key(self):
        # An API key is NOT an argument to validate_allowance and cannot stand in for a confirmed
        # amount/expiry; the only way to get an allowance is explicit confirmation. There is no
        # code path that turns a key into an allowance — confirm the signature has no key param.
        import inspect

        params = set(inspect.signature(validate_allowance).parameters)
        self.assertNotIn("api_key", params)
        self.assertNotIn("key", params)
        self.assertEqual({"amount", "expires_at", "paid_budget", "now"}, params)

    def test_allowance_from_set_routes_through_validation(self):
        req = AllowanceSet(
            confirmed_usd=Decimal("3"),
            expires_at=FUTURE,
            model="gpt-4.1-mini-2025-04-14",
            input_usd_per_million=Decimal("0.15"),
            output_usd_per_million=Decimal("0.6"),
        )
        allowance = allowance_from_set(req, now=NOW)
        self.assertEqual(allowance.amount_usd, Decimal("3"))
        # An expired AllowanceSet is rejected by the same hard block.
        req_expired = AllowanceSet(
            confirmed_usd=Decimal("3"),
            expires_at=PAST,
            model="m",
            input_usd_per_million=Decimal("0"),
            output_usd_per_million=Decimal("0"),
        )
        with self.assertRaises(PartsIQError):
            allowance_from_set(req_expired, now=NOW)

    def test_allowance_view_enabled_only_with_live_confirmation(self):
        live = CreditAllowance(amount_usd=Decimal("5"), expires_at=FUTURE, paid_budget_usd=Decimal("0"))
        view = allowance_view(
            live, consumed_usd=Decimal("1"), reserved_usd=Decimal("0.5"), model="m", now=NOW
        )
        self.assertTrue(view.enabled)
        self.assertEqual(view.confirmed_usd, Decimal("5"))
        self.assertEqual(view.consumed_usd, Decimal("1"))

        expired = CreditAllowance(amount_usd=Decimal("5"), expires_at=PAST, paid_budget_usd=Decimal("0"))
        self.assertFalse(
            allowance_view(expired, consumed_usd=Decimal("0"), reserved_usd=Decimal("0"), model="m", now=NOW).enabled
        )
        none_view = allowance_view(
            None, consumed_usd=Decimal("0"), reserved_usd=Decimal("0"), model=None, now=NOW
        )
        self.assertFalse(none_view.enabled)
        self.assertEqual(none_view.confirmed_usd, Decimal(0))


# --------------------------------------------------------------------------- live (BLOCKED)


@unittest.skipUnless(
    os.environ.get("PARTSIQ_LIVE_INFRA") == "1",
    "live Snowflake reporter + live Langfuse are BLOCKED offline; run only when PARTSIQ_LIVE_INFRA=1",
)
class LiveReporting(unittest.TestCase):  # pragma: no cover - integration gate
    def test_live_snowflake_reporter(self):
        self.fail("live Snowflake reporter export is integration work (BLOCKED: no connector/allowance)")


def test_modules_import_without_optional_deps():
    # langfuse and snowflake-connector-python are NOT installed; the modules still import.
    assert outbox_mod.redact_event is not None
    assert service_mod.get_metrics is not None


if __name__ == "__main__":
    unittest.main(verbosity=2)
