"""Collect a schema receipt from a live database.

Contract (FLOW.md row 03):
    async def collect_schema_receipt(dsn: str) -> SchemaReceipt

The receipt records the ACTUAL managed Postgres version, installed extensions,
columns, indexes and RLS policies, so the kit never falsely fixes managed versions
(docs/TECH_SPEC.md section 3). It is read-only.

The catalog queries are injected via a `fetch` callable so the shape can be tested
offline; against a real database the default psycopg fetch is used.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from partsiq_common.contracts import SchemaReceipt

Fetch = Callable[[str], Awaitable[list[tuple]]]

_Q_VERSION = "SHOW server_version"
_Q_EXTENSIONS = "SELECT extname, extversion FROM pg_extension ORDER BY extname"
_Q_COLUMNS = (
    "SELECT table_name, column_name FROM information_schema.columns "
    "WHERE table_schema='public' ORDER BY table_name, ordinal_position"
)
_Q_INDEXES = "SELECT tablename, indexname FROM pg_indexes WHERE schemaname='public' ORDER BY tablename, indexname"
_Q_POLICIES = "SELECT tablename, policyname FROM pg_policies WHERE schemaname='public' ORDER BY tablename, policyname"


def _group(rows: list[tuple]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for key, value in rows:
        grouped.setdefault(key, []).append(value)
    return grouped


async def collect_schema_receipt(dsn: str, *, fetch: Fetch | None = None) -> SchemaReceipt:
    """Return a SchemaReceipt describing the database at `dsn`."""
    if fetch is None:  # pragma: no cover - needs a live DB
        fetch = await _psycopg_fetch(dsn)

    version_rows = await fetch(_Q_VERSION)
    extensions = {name: version for name, version in await fetch(_Q_EXTENSIONS)}
    return SchemaReceipt(
        postgres_version=str(version_rows[0][0]) if version_rows else "unknown",
        extensions=extensions,
        columns=_group(await fetch(_Q_COLUMNS)),
        indexes=_group(await fetch(_Q_INDEXES)),
        policies=_group(await fetch(_Q_POLICIES)),
    )


async def _psycopg_fetch(dsn: str) -> Fetch:  # pragma: no cover - needs a live DB
    import psycopg

    async def fetch(query: str) -> list[tuple]:
        async with await psycopg.AsyncConnection.connect(dsn) as conn:
            cur = await conn.execute(query)
            rows: list[tuple] = await cur.fetchall()
            return rows

    return fetch
