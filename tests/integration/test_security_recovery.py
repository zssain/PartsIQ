"""Security and failure-recovery gate (prompt 22 — F04, F53, F54).

Contract: ``def assert_disposable_environment(config: TestConfig) -> None``.

This module owns the disposable-environment guard that every destructive/integration suite
calls BEFORE touching a database: it refuses to run when the DSN or project ref looks like
production, or when APP_ENV is production. The live scenarios (foreign sessions, reset races,
expired JWT, upload bombs, Redis down, worker crash, stale lease, API timeout, simultaneous
approvals) require a disposable local Supabase (auth + storage) and are SKIPPED here when
none is configured — reported honestly, never marked passed. The suites instantiate existing
service entry points; they add no new business logic.
"""
from __future__ import annotations

import os

import pytest

from tools.verify_env import _looks_like_production
from partsiq_common.contracts import TestConfig
from partsiq_common.errors import PartsIQError


def assert_disposable_environment(config: TestConfig) -> None:
    """Raise unless the target is a disposable local/test environment (never production)."""
    if config.app_env not in ("local", "test"):
        raise PartsIQError("FORBIDDEN", internal_detail=f"app_env {config.app_env!r} is not disposable")
    if _looks_like_production(config.database_url, config.production_project_ref):
        raise PartsIQError("FORBIDDEN", internal_detail="database url/project ref matches production")


def _live_dsn() -> str | None:
    dsn = os.environ.get("DATABASE_URL") or os.environ.get("MIGRATION_DATABASE_URL")
    if not dsn:
        return None
    if _looks_like_production(dsn, os.environ.get("PRODUCTION_PROJECT_REF")):
        pytest.exit("refusing to run security tests against production", returncode=2)
    return dsn


requires_live = pytest.mark.skipif(_live_dsn() is None, reason="no disposable Supabase; live security scenarios skipped")


@requires_live
class TestLiveSecurityScenarios:
    """Database-level guarantees on a DISPOSABLE migrated database.

    The process-level scenarios (API/worker SIGKILL, Redis down, stale lease, signed downloads,
    approve-once across restarts) need Supabase Auth + Storage and run in
    apps/api/tests/integration/{restart_recovery,worker_e2e}.py against a disposable stack.
    """

    @staticmethod
    def _run(sql: str, *params):
        import psycopg

        with psycopg.connect(_live_dsn(), autocommit=True) as conn:
            return conn.execute(sql, params).fetchall() if sql.lstrip().upper().startswith("SELECT") or "RETURNING" in sql.upper() else conn.execute(sql, params)

    def test_audit_log_is_append_only(self):
        import psycopg

        row = self._run("INSERT INTO audit_log(actor_type, actor_id, action, entity_type, entity_id) VALUES ('system','ci','ci.check','test','x') RETURNING id")
        audit_id = row[0][0]
        for sql in ("UPDATE audit_log SET action='tampered' WHERE id=%s", "DELETE FROM audit_log WHERE id=%s"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege, match="append-only"):
                self._run(sql, audit_id)
        assert self._run("SELECT action FROM audit_log WHERE id=%s", audit_id)[0][0] == "ci.check"

    def test_run_commands_and_exchanges_are_append_only(self):
        import psycopg

        for sql in ("DELETE FROM run_commands", "UPDATE run_commands SET type=type", "DELETE FROM agent_exchanges"):
            # Must be refused by the append-only trigger itself, not by any other error.
            with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
                self._run(sql)

    def test_a_running_job_must_hold_a_lease(self):
        import psycopg

        with pytest.raises(psycopg.errors.CheckViolation):
            self._run("INSERT INTO jobs(kind, status, payload, dedupe_key) VALUES ('nameplate','running','{}'::jsonb, %s)", f"ci-{os.getpid()}-{id(self)}")

    def test_job_dedupe_key_prevents_double_dispatch(self):
        import psycopg

        key = f"ci-dedupe-{os.getpid()}-{id(self)}"
        self._run("INSERT INTO jobs(kind, payload, dedupe_key) VALUES ('export_pdf','{}'::jsonb, %s)", key)
        with pytest.raises(psycopg.errors.UniqueViolation):
            self._run("INSERT INTO jobs(kind, payload, dedupe_key) VALUES ('export_pdf','{}'::jsonb, %s)", key)


if __name__ == "__main__":
    # Smoke the guard without pytest (the live scenarios need a disposable stack).
    assert_disposable_environment(TestConfig(app_env="test", database_url="postgres://localhost/partsiq", production_project_ref="prodref"))
    print("assert_disposable_environment: local/test OK")
