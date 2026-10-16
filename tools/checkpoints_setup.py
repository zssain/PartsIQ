"""One-time LangGraph checkpoint schema setup (migration time only).

Contract (FLOW.md row 03):
    async def setup_checkpoints(dsn: str) -> None
    # no application service invokes this.

The four checkpoint tables use the exact extracted DDL from
langgraph-checkpoint-postgres 3.0.4 (spec/sql/006). We apply that DDL directly rather
than importing the library at migration time (prompt 03 adds no new package), because
006 contains CREATE INDEX CONCURRENTLY statements that must run OUTSIDE a transaction
(autocommit). Afterwards 007 applies the checkpoint RLS/grants inside a transaction and
leaves the runtime orchestrator role with DML only — no DDL (CONSTRAINTS.md rule 11).

Run with MIGRATION_DATABASE_URL. Never resets a database.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from tools.apply_catalogue_schema import assert_not_reset

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_SQL_DIR = REPO_ROOT / "spec" / "sql"
LIBRARY_SQL = SPEC_SQL_DIR / "006_checkpoint_library.sql"
PERMISSIONS_SQL = SPEC_SQL_DIR / "007_checkpoint_permissions.sql"

# An executor runs one SQL string. The autocommit executor must NOT wrap statements in
# a transaction (required for CREATE INDEX CONCURRENTLY).
Executor = Callable[[str], Awaitable[None]]


def split_statements(sql: str) -> list[str]:
    """Split a SQL script into non-empty, comment-stripped statements."""
    statements: list[str] = []
    for raw in sql.split(";"):
        lines = [ln for ln in raw.splitlines() if not ln.strip().startswith("--")]
        cleaned = "\n".join(lines).strip()
        if cleaned:
            statements.append(cleaned)
    return statements


async def setup_checkpoints(
    dsn: str,
    *,
    autocommit_exec: Executor | None = None,
    tx_exec: Executor | None = None,
) -> None:
    """Create the checkpoint schema (autocommit) then apply its permissions (transaction)."""
    assert_not_reset([dsn])
    if autocommit_exec is None or tx_exec is None:  # pragma: no cover - needs a live DB
        autocommit_exec, tx_exec = await _psycopg_executors(dsn)

    # 1. Library DDL: each statement in autocommit so CONCURRENTLY indexes succeed.
    for statement in split_statements(LIBRARY_SQL.read_text(encoding="utf-8")):
        await autocommit_exec(statement)

    # 2. Permissions: 007 is already a single BEGIN..COMMIT block; run it as one unit.
    await tx_exec(PERMISSIONS_SQL.read_text(encoding="utf-8"))


async def _psycopg_executors(dsn: str) -> tuple[Executor, Executor]:  # pragma: no cover
    """Build real psycopg executors (used only against a live migration database)."""
    import psycopg

    async def autocommit_exec(statement: str) -> None:
        async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
            await conn.execute(statement)

    async def tx_exec(script: str) -> None:
        async with await psycopg.AsyncConnection.connect(dsn) as conn:
            async with conn.transaction():
                for statement in split_statements(script):
                    if statement.upper() in ("BEGIN", "COMMIT"):
                        continue
                    await conn.execute(statement)

    return autocommit_exec, tx_exec
