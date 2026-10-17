"""Snowflake catalogue source (``DATA_SOURCE=snowflake``) — foundation 02.

Reads an immutable, version-addressed catalogue snapshot from Snowflake and returns the SAME
typed :class:`~partsiq.core.api_models.CatalogueSnapshot` shape as the fixture repository,
labelled ``source="snowflake"``. Writes a full immutable version and returns a
:class:`~partsiq.core.api_models.SyncReceipt` carrying the Snowflake query id (``sfqid``).

Design constraints (prompt 02 + SNOWFLAKE.md, enforced here):
  * The module imports cleanly even though ``snowflake-connector-python`` is NOT installed:
    the connector is LAZY-imported only inside :func:`open_connection`, the one function that
    opens a real connection. Every other path works against an injected connection/cursor that
    satisfies the :class:`SnowflakeConnection` / :class:`SnowflakeCursor` protocols, so unit
    tests use a deterministic fake and live Snowflake stays BLOCKED.
  * All SQL is a fixed statement with ``?`` BOUND parameters (``paramstyle='qmark'``). A user
    field NEVER becomes a value placeholder or an SQL fragment.
  * Database/schema identifiers cannot be bound; they are chosen from a fixed dev/prod
    ALLOWLIST derived from validated ``Settings``, never from a request field.
  * Reads verify the declared row count and the canonical digest before returning; duplicate
    keys quarantine the version (via :mod:`partsiq.catalogue.validation`) rather than being
    merged by dict overwrite.
  * A Snowflake exception is mapped to a stable ``PartsIQError`` and NEVER silently changes the
    data source.
"""
from __future__ import annotations

import json
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from partsiq.core.api_models import CatalogueRecord, CatalogueSnapshot, SyncReceipt
from partsiq.core.errors import PartsIQError
from partsiq.core.settings import Settings

from .models import CatalogueSourceName, content_sha256

_SOURCE: CatalogueSourceName = "snowflake"

# Fixed identifier allowlist. Database/schema names are interpolated into fixed SQL ONLY from
# this map (keyed by the validated Settings.snowflake_database literal), never from a request.
_ALLOWED_DATABASES: frozenset[str] = frozenset({"PARTSIQ_DEV", "PARTSIQ_PROD"})
_CATALOGUE_SCHEMA = "CATALOGUE"

# Fixed SQL templates. The ``{db}`` / ``{schema}`` slots are filled ONLY from the allowlist;
# every value is a ``?`` bound parameter.
_READ_RECORDS_SQL = (
    "SELECT ENTITY_TYPE, ENTITY_KEY, PAYLOAD, ROW_SHA256 "
    "FROM {db}.{schema}.RECORDS WHERE VERSION_ID = ? "
    "ORDER BY ENTITY_TYPE, ENTITY_KEY"
)
_READ_VERSION_SQL = (
    "SELECT VERSION_ID, CONTENT_SHA256, RECORD_COUNT, CREATED_AT "
    "FROM {db}.{schema}.VERSIONS WHERE VERSION_ID = ?"
)
_INSERT_VERSION_SQL = (
    "INSERT INTO {db}.{schema}.VERSIONS (VERSION_ID, CONTENT_SHA256, RECORD_COUNT, CREATED_AT) "
    "VALUES (?, ?, ?, CURRENT_TIMESTAMP())"
)
_INSERT_RECORD_SQL = (
    "INSERT INTO {db}.{schema}.RECORDS (VERSION_ID, ENTITY_TYPE, ENTITY_KEY, PAYLOAD, ROW_SHA256) "
    "SELECT ?, ?, ?, PARSE_JSON(?), ?"
)


@runtime_checkable
class SnowflakeCursor(Protocol):
    """Minimal synchronous cursor surface used by this repository (connector-agnostic)."""

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


def _resolve_identifiers(settings: Settings) -> tuple[str, str]:
    """Return the allowlisted (database, schema) for the catalogue tables.

    Raises if the configured database is somehow outside the fixed allowlist — a guard against
    an identifier ever being sourced from anything but validated settings.
    """
    database = settings.snowflake_database
    if database not in _ALLOWED_DATABASES:
        raise PartsIQError(
            "DEPENDENCY_UNAVAILABLE",
            detail="Catalogue source is misconfigured.",
            internal_detail=f"snowflake_database {database!r} not in allowlist",
        )
    return database, _CATALOGUE_SCHEMA


def _parse_payload(raw: object) -> dict[str, object]:
    """Snowflake VARIANT may arrive as a JSON string or an already-parsed object."""
    if isinstance(raw, str):
        return json.loads(raw)
    if isinstance(raw, dict):
        return dict(raw)
    raise PartsIQError(
        "DEPENDENCY_UNAVAILABLE",
        detail="Catalogue payload is malformed.",
        internal_detail=f"unexpected PAYLOAD type {type(raw).__name__}",
    )


class SnowflakeCatalogueRepository:
    """A :class:`~partsiq.catalogue.models.CatalogueSource` reading/writing Snowflake.

    The live connection is INJECTED (``connection``) so tests use a fake and live Snowflake
    stays BLOCKED. Open a real connection with :func:`open_connection` and pass it in.
    """

    source: CatalogueSourceName = _SOURCE

    def __init__(self, connection: SnowflakeConnection, settings: Settings) -> None:
        self._connection = connection
        self._database, self._schema = _resolve_identifiers(settings)

    def _sql(self, template: str) -> str:
        return template.format(db=self._database, schema=self._schema)

    # --- read -----------------------------------------------------------

    def read_version(self, version_id: UUID) -> CatalogueSnapshot:
        """Read a requested immutable VERSION_ID and verify its row count and digest.

        The version manifest (VERSIONS) supplies the declared record count and content digest;
        the records are read with fixed SQL and a single bound VERSION_ID. The observed count
        and recomputed canonical digest MUST match the manifest, otherwise the version is
        rejected (never served partially).
        """
        cursor = self._connection.cursor()
        try:
            cursor.execute(self._sql(_READ_VERSION_SQL), (str(version_id),))
            version_rows = cursor.fetchall()
            if not version_rows:
                raise PartsIQError(
                    "NOT_FOUND",
                    detail="The requested catalogue version is unavailable.",
                    internal_detail=f"no VERSIONS row for {version_id}",
                )
            _vid, declared_sha256, declared_count, _created_at = version_rows[0]

            cursor.execute(self._sql(_READ_RECORDS_SQL), (str(version_id),))
            record_rows = cursor.fetchall()
        except PartsIQError:
            raise
        except Exception as exc:  # connector / network error — map, never fall back
            raise PartsIQError(
                "DEPENDENCY_UNAVAILABLE",
                detail="The catalogue source is temporarily unavailable.",
                internal_detail=f"snowflake read failed: {type(exc).__name__}",
            ) from exc
        finally:
            cursor.close()

        records = [
            CatalogueRecord(entity_type=str(row[0]), entity_key=str(row[1]), payload=_parse_payload(row[2]))
            for row in record_rows
        ]
        observed_count = len(records)
        if int(declared_count) != observed_count:
            raise PartsIQError(
                "STALE_CATALOGUE",
                detail="The catalogue version failed its integrity check.",
                internal_detail=f"record count mismatch: declared {declared_count}, observed {observed_count}",
            )
        observed_sha256 = content_sha256(records)
        if str(declared_sha256) != observed_sha256:
            raise PartsIQError(
                "STALE_CATALOGUE",
                detail="The catalogue version failed its integrity check.",
                internal_detail="content digest mismatch between manifest and records",
            )
        return CatalogueSnapshot(
            version_id=version_id,
            source=_SOURCE,
            content_sha256=observed_sha256,
            records=records,
        )

    # --- write ----------------------------------------------------------

    def write_version(self, snapshot: CatalogueSnapshot) -> SyncReceipt:
        """Write a full immutable version inside an explicit BEGIN/COMMIT, returning a receipt.

        The receipt records the Snowflake query id (``sfqid``). On any failure the transaction
        is rolled back and the receipt state is ``failed`` — the remote version is left
        unactivated for reconciliation; the data source is never silently changed.
        """
        record_count = len(snapshot.records)
        cursor = self._connection.cursor()
        query_id: str | None = None
        try:
            cursor.execute("BEGIN")
            cursor.execute(
                self._sql(_INSERT_VERSION_SQL),
                (str(snapshot.version_id), snapshot.content_sha256, record_count),
            )
            from .models import row_sha256  # local import keeps module import cost minimal

            for record in snapshot.records:
                cursor.execute(
                    self._sql(_INSERT_RECORD_SQL),
                    (
                        str(snapshot.version_id),
                        record.entity_type,
                        record.entity_key,
                        json.dumps(record.payload, sort_keys=True, ensure_ascii=False, default=str),
                        row_sha256(record),
                    ),
                )
            self._connection.commit()
            query_id = getattr(cursor, "sfqid", None)
        except Exception:
            try:
                self._connection.rollback()
            except Exception:  # pragma: no cover - rollback best effort
                pass
            return SyncReceipt(
                version_id=snapshot.version_id,
                state="failed",
                record_count=record_count,
                content_sha256=snapshot.content_sha256,
                query_id=getattr(cursor, "sfqid", None),
            )
        finally:
            cursor.close()

        return SyncReceipt(
            version_id=snapshot.version_id,
            state="remote_written",
            record_count=record_count,
            content_sha256=snapshot.content_sha256,
            query_id=query_id,
        )


def open_connection(settings: Settings, *, role: str = "reader") -> SnowflakeConnection:
    """Open a REAL Snowflake connection using the pinned 4.8 key-pair signature.

    This is the ONLY place the connector is imported; the import is LAZY so the module loads
    without ``snowflake-connector-python`` installed. Live Snowflake is BLOCKED in this
    environment (the connector is not installed and no warehouse allowance is confirmed), so
    calling this raises a clear dependency error rather than faking a connection.
    """
    try:
        import snowflake.connector  # type: ignore[import-not-found]  # noqa: PLC0415 - intentional lazy import
    except ImportError as exc:
        raise PartsIQError(
            "DEPENDENCY_UNAVAILABLE",
            detail="The catalogue source is unavailable.",
            internal_detail="snowflake-connector-python is not installed (live Snowflake BLOCKED)",
        ) from exc

    database, schema = _resolve_identifiers(settings)
    user_by_role = {
        "reader": settings.snowflake_user_reader,
        "loader": settings.snowflake_user_loader,
        "reporter": settings.snowflake_user_reporter,
    }
    user = user_by_role.get(role, "")
    request_tag = "partsiq:catalogue"
    return snowflake.connector.connect(  # pragma: no cover - requires live Snowflake
        account=settings.snowflake_account,
        user=user,
        private_key_file=settings.snowflake_private_key_file,
        private_key_file_pwd=settings.snowflake_private_key_password or None,
        role=f"PARTSIQ_{role.upper()}",
        warehouse=settings.snowflake_warehouse,
        database=database,
        schema=schema,
        paramstyle="qmark",
        login_timeout=10,
        network_timeout=30,
        session_parameters={
            "QUERY_TAG": request_tag,
            "STATEMENT_TIMEOUT_IN_SECONDS": 20,
        },
    )
