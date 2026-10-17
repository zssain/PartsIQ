"""The Snowflake reporting sink for the analytics outbox (foundation 23, F63).

Ships redacted outbox rows to Snowflake's ``REPORTING.EVENTS`` table with a FIXED, idempotent
``EVENT_ID`` MERGE and bound parameters. Mirrors the catalogue Snowflake repository's safety
model (``partsiq.catalogue.snowflake_repository``):

  * The connector is LAZY-imported only inside :func:`open_connection`; the module loads
    cleanly even though ``snowflake-connector-python`` is NOT installed. Every other path runs
    against an INJECTED connection that satisfies :class:`SnowflakeConnection`, so unit tests
    use a deterministic fake and live Snowflake stays BLOCKED (no confirmed warehouse
    allowance; connector absent).
  * All SQL is a fixed statement with ``?`` BOUND parameters (``paramstyle='qmark'``). An
    event field NEVER becomes a value placeholder or an SQL fragment.
  * Database/schema/table identifiers are chosen from a fixed dev/prod ALLOWLIST derived from
    validated :class:`~partsiq.core.settings.Settings`, never from a request or an event.
  * The MERGE is idempotent on ``EVENT_ID``: re-shipping the same batch updates rather than
    duplicates, so a crash before acknowledgement safely repeats the same event.
  * A Snowflake exception yields a non-succeeded :class:`AnalyticsSyncReceipt` (rows stay
    pending in the outbox) and NEVER an empty successful result (prompt 23 VALIDATION).
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
from uuid import UUID, uuid4

from partsiq.core.api_models import AnalyticsSyncReceipt
from partsiq.core.errors import PartsIQError
from partsiq.core.settings import Settings

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids an import cycle at runtime
    from partsiq.analytics.outbox import OutboxRow

# Fixed identifier allowlist. The database name is interpolated into fixed SQL ONLY from this
# map (keyed by the validated Settings.snowflake_database literal), never from a request/event.
_ALLOWED_DATABASES: frozenset[str] = frozenset({"PARTSIQ_DEV", "PARTSIQ_PROD"})
_REPORTING_SCHEMA = "REPORTING"
_EVENTS_TABLE = "EVENTS"

# Idempotent upsert keyed on EVENT_ID. A standard PK does not dedupe an INSERT; an explicit
# MERGE on EVENT_ID does — a repeated batch updates the matched row instead of adding a copy.
# Only allowlisted reporting columns are written; identity/messages/serials/notes are absent.
_MERGE_SQL = (
    "MERGE INTO {db}.{schema}.{table} AS target "
    "USING (SELECT ? AS EVENT_ID, ? AS EVENT_TYPE, ? AS OCCURRED_AT, ? AS IS_DEMO, "
    "? AS STATUS, ? AS STAGE, ? AS DURATION_MS, ? AS INPUT_TOKENS, ? AS OUTPUT_TOKENS, "
    "? AS ESTIMATED_COST_USD) AS source "
    "ON target.EVENT_ID = source.EVENT_ID "
    "WHEN MATCHED THEN UPDATE SET "
    "EVENT_TYPE = source.EVENT_TYPE, OCCURRED_AT = source.OCCURRED_AT, "
    "IS_DEMO = source.IS_DEMO, STATUS = source.STATUS, STAGE = source.STAGE, "
    "DURATION_MS = source.DURATION_MS, INPUT_TOKENS = source.INPUT_TOKENS, "
    "OUTPUT_TOKENS = source.OUTPUT_TOKENS, ESTIMATED_COST_USD = source.ESTIMATED_COST_USD "
    "WHEN NOT MATCHED THEN INSERT "
    "(EVENT_ID, EVENT_TYPE, OCCURRED_AT, IS_DEMO, STATUS, STAGE, DURATION_MS, "
    "INPUT_TOKENS, OUTPUT_TOKENS, ESTIMATED_COST_USD) "
    "VALUES (source.EVENT_ID, source.EVENT_TYPE, source.OCCURRED_AT, source.IS_DEMO, "
    "source.STATUS, source.STAGE, source.DURATION_MS, source.INPUT_TOKENS, "
    "source.OUTPUT_TOKENS, source.ESTIMATED_COST_USD)"
)

# Duplicate-diagnostics query (prompt 23 step 5) — counts any EVENT_IDs with more than one row.
_DUPLICATE_DIAGNOSTIC_SQL = (
    "SELECT EVENT_ID, COUNT(*) AS N FROM {db}.{schema}.{table} "
    "GROUP BY EVENT_ID HAVING COUNT(*) > 1"
)


@runtime_checkable
class SnowflakeCursor(Protocol):
    """Minimal synchronous cursor surface used by this sink (connector-agnostic)."""

    sfqid: str | None

    def execute(self, command: str, params: object | None = ...) -> object: ...

    def fetchall(self) -> list[Any]: ...

    def close(self) -> None: ...


@runtime_checkable
class SnowflakeConnection(Protocol):
    """Minimal synchronous connection surface (what the connector's ``Connection`` provides)."""

    def cursor(self) -> SnowflakeCursor: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...


def _resolve_identifiers(settings: Settings) -> tuple[str, str, str]:
    """Return the allowlisted (database, schema, table) for the reporting events table."""
    database = settings.snowflake_database
    if database not in _ALLOWED_DATABASES:
        raise PartsIQError(
            "DEPENDENCY_UNAVAILABLE",
            detail="Analytics reporting is misconfigured.",
            internal_detail=f"snowflake_database {database!r} not in allowlist",
        )
    return database, _REPORTING_SCHEMA, _EVENTS_TABLE


def _bind_values(row: "OutboxRow") -> tuple[object, ...]:
    """Build the bound parameter tuple for one row from its redacted allowlisted payload."""
    payload = row.payload
    occurred = row.occurred_at
    occurred_iso = occurred.isoformat() if isinstance(occurred, datetime) else str(occurred)
    cost = payload.get("estimated_cost_usd")
    return (
        str(row.event_id),
        row.event_type,
        occurred_iso,
        bool(row.is_demo),
        payload.get("status"),
        payload.get("stage"),
        payload.get("duration_ms"),
        payload.get("input_tokens"),
        payload.get("output_tokens"),
        str(cost) if cost is not None else None,
    )


class SnowflakeReporter:
    """A :class:`~partsiq.analytics.outbox.ReportingSink` that MERGEs events into Snowflake.

    The live connection is INJECTED so tests use a fake and live Snowflake stays BLOCKED. Open
    a real connection with :func:`open_connection` and pass it in.
    """

    source = "snowflake"

    def __init__(self, connection: SnowflakeConnection, settings: Settings) -> None:
        self._connection = connection
        self._database, self._schema, self._table = _resolve_identifiers(settings)

    def _sql(self, template: str) -> str:
        return template.format(db=self._database, schema=self._schema, table=self._table)

    def merge_events(self, rows: list["OutboxRow"]) -> AnalyticsSyncReceipt:
        """Idempotently MERGE a batch of redacted rows by ``EVENT_ID`` inside one transaction.

        On success the transaction commits and the receipt carries the Snowflake query id
        (``sfqid``) with ``succeeded=True``. On ANY failure the transaction rolls back and the
        receipt is ``succeeded=False`` — the outbox keeps the rows pending (never acknowledged),
        so no event is lost and no empty success is reported.
        """
        run_id = uuid4()
        cursor = self._connection.cursor()
        query_id: str | None = None
        try:
            cursor.execute("BEGIN")
            for row in rows:
                cursor.execute(self._sql(_MERGE_SQL), _bind_values(row))
            self._connection.commit()
            query_id = getattr(cursor, "sfqid", None)
        except Exception:
            try:
                self._connection.rollback()
            except Exception:  # pragma: no cover - rollback best effort
                pass
            return AnalyticsSyncReceipt(
                run_id=run_id,
                row_count=0,
                query_id=getattr(cursor, "sfqid", None),
                succeeded=False,
            )
        finally:
            cursor.close()
        return AnalyticsSyncReceipt(
            run_id=run_id, row_count=len(rows), query_id=query_id, succeeded=True
        )

    def duplicate_event_ids(self) -> list[tuple[UUID, int]]:
        """Run duplicate diagnostics (prompt 23 step 5): EVENT_IDs present more than once."""
        cursor = self._connection.cursor()
        try:
            cursor.execute(self._sql(_DUPLICATE_DIAGNOSTIC_SQL), ())
            fetched = cursor.fetchall()
        except Exception as exc:
            raise PartsIQError(
                "DEPENDENCY_UNAVAILABLE",
                detail="Analytics reporting is temporarily unavailable.",
                internal_detail=f"snowflake duplicate diagnostic failed: {type(exc).__name__}",
            ) from exc
        finally:
            cursor.close()
        return [(UUID(str(r[0])), int(r[1])) for r in fetched]


def serialize_payload(payload: dict[str, object]) -> str:
    """Deterministic JSON for an optional raw-payload column (sorted keys, Decimal-safe)."""
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)


def open_connection(settings: Settings) -> SnowflakeConnection:
    """Open a REAL Snowflake reporter connection using the pinned 4.8 key-pair signature.

    This is the ONLY place the connector is imported; the import is LAZY so the module loads
    without ``snowflake-connector-python`` installed. Live Snowflake is BLOCKED in this
    environment (the connector is not installed and no reporting-warehouse allowance is
    confirmed), so calling this raises a clear dependency error rather than faking a connection.
    """
    try:
        import snowflake.connector  # type: ignore[import-not-found]  # noqa: PLC0415 - lazy import
    except ImportError as exc:
        raise PartsIQError(
            "DEPENDENCY_UNAVAILABLE",
            detail="Analytics reporting is unavailable.",
            internal_detail="snowflake-connector-python is not installed (live Snowflake BLOCKED)",
        ) from exc

    database, schema, _table = _resolve_identifiers(settings)
    return snowflake.connector.connect(  # pragma: no cover - requires live Snowflake
        account=settings.snowflake_account,
        user=settings.snowflake_user_reporter,
        private_key_file=settings.snowflake_private_key_file,
        private_key_file_pwd=settings.snowflake_private_key_password or None,
        role="PARTSIQ_REPORTER",
        warehouse=settings.snowflake_warehouse,
        database=database,
        schema=schema,
        paramstyle="qmark",
        login_timeout=10,
        network_timeout=30,
        session_parameters={
            "QUERY_TAG": "partsiq:analytics",
            "STATEMENT_TIMEOUT_IN_SECONDS": 20,
        },
    )
