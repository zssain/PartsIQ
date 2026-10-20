"""Additive collaboration migration against a DISPOSABLE PostgreSQL (skips without one).

Run with a throwaway database, e.g.::

    docker run -d --rm --name pq-pg -e POSTGRES_PASSWORD=pq -p 55432:5432 postgres:16
    PARTSIQ_TEST_PG_DSN=postgresql://postgres:pq@localhost:55432/postgres uv run --all-packages pytest apps/api/tests/test_collaboration_migration.py

Only the referenced tables are stubbed (profiles, enquiries, catalogue_versions, demo_sessions);
the real chain is applied by the owner's migration command. Never point this at a shared DB.
"""
from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest

DSN = os.environ.get("PARTSIQ_TEST_PG_DSN", "")
MIGRATION = Path(__file__).resolve().parents[3] / "supabase" / "migrations" / "20261020000100_agent_collaboration.sql"

pytestmark = pytest.mark.skipif(not DSN, reason="PARTSIQ_TEST_PG_DSN not set (disposable PostgreSQL required)")

STUBS = """
DROP SCHEMA IF EXISTS pqtest CASCADE; CREATE SCHEMA pqtest; SET search_path = pqtest, public;
CREATE SCHEMA IF NOT EXISTS app_private;
CREATE TABLE profiles (id uuid PRIMARY KEY);
CREATE TABLE catalogue_versions (id uuid PRIMARY KEY);
CREATE TABLE demo_sessions (id uuid PRIMARY KEY);
CREATE TABLE enquiries (id uuid PRIMARY KEY);
"""


async def _conn():
    import asyncpg

    if "localhost" not in DSN and "127.0.0.1" not in DSN:
        pytest.skip("refusing a non-local database for a destructive test")
    conn = await asyncpg.connect(DSN)
    await conn.execute(STUBS)
    await conn.execute("SET search_path = pqtest, public")
    await conn.execute(MIGRATION.read_text())
    return conn


async def test_migration_applies_and_enforces_run_invariants() -> None:
    import asyncpg

    conn = await _conn()
    try:
        user, version, enquiry = uuid4(), uuid4(), uuid4()
        await conn.execute("INSERT INTO profiles VALUES ($1)", user)
        await conn.execute("INSERT INTO catalogue_versions VALUES ($1)", version)
        await conn.execute("INSERT INTO enquiries VALUES ($1)", enquiry)
        run = await conn.fetchval(
            "INSERT INTO workflow_runs(enquiry_id,revision,mode,status,execution_source,created_by,catalogue_version_id,limits) "
            "VALUES ($1,1,'collaboration','running','fixture',$2,$3,'{}') RETURNING id", enquiry, user, version)
        # One active run per (enquiry, revision): a second concurrent run is refused.
        with pytest.raises(asyncpg.UniqueViolationError):
            await conn.execute(
                "INSERT INTO workflow_runs(enquiry_id,revision,mode,status,execution_source,created_by,catalogue_version_id,limits) "
                "VALUES ($1,1,'guided','queued','fixture',$2,$3,'{}')", enquiry, user, version)
        # Ordered exchanges: duplicate sequence numbers are impossible.
        ins = "INSERT INTO agent_exchanges(run_id,seq,sender,recipient,kind,summary,source,status) VALUES ($1,$2,$3,$4,$5,$6,'fixture','delivered')"
        await conn.execute(ins, run, 1, "controller", "intake", "task", "New enquiry")
        with pytest.raises(asyncpg.UniqueViolationError):
            await conn.execute(ins, run, 1, "intake", "parts", "handoff", "dup seq")
        # Unknown participants/kinds are rejected by the schema too (defence in depth).
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(ins, run, 2, "intake", "everyone", "handoff", "broadcast")
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(ins, run, 3, "parts", "reply", "approve_reply", "write tool")
        # Exchanges are append-only.
        with pytest.raises(asyncpg.RaiseError):
            await conn.execute("DELETE FROM agent_exchanges WHERE run_id=$1", run)
        # Commands: idempotent per (run, key); append-only.
        cmd = "INSERT INTO run_commands(run_id,actor_id,type,expected_revision,idempotency_key,payload_sha256,accepted,result) VALUES ($1,$2,'pause',1,$3,$4,true,'paused')"
        key = uuid4()
        await conn.execute(cmd, run, user, key, "a" * 64)
        with pytest.raises(asyncpg.UniqueViolationError):
            await conn.execute(cmd, run, user, key, "b" * 64)
        with pytest.raises(asyncpg.RaiseError):
            await conn.execute("UPDATE run_commands SET result='x'")
        # One open pending action per run.
        pa = "INSERT INTO pending_actions(run_id,enquiry_id,revision,kind,requested_by,prompt,allowed_resolutions) VALUES ($1,$2,1,'delegation_consent','parts','May I?','{approve,deny}')"
        await conn.execute(pa, run, enquiry)
        with pytest.raises(asyncpg.UniqueViolationError):
            await conn.execute(pa, run, enquiry)
        # A blocked run must say why.
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute("UPDATE workflow_runs SET status='blocked' WHERE id=$1", run)
    finally:
        await conn.execute("DROP SCHEMA pqtest CASCADE")
        await conn.close()
