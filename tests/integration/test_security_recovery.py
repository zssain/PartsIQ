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
    """Foreign sessions, reset races, expired JWT, upload bombs, Redis down, worker crash,
    stale lease, API timeout and simultaneous approvals — against a disposable local stack.
    BLOCKED here (no live Supabase); each would instantiate the existing gateway/worker/
    orchestrator entry points without new business logic."""

    def test_placeholder_requires_live_stack(self):  # pragma: no cover - skipped offline
        raise AssertionError("live security scenarios must run against a disposable local Supabase")


if __name__ == "__main__":
    # Smoke the guard without pytest (the live scenarios need a disposable stack).
    assert_disposable_environment(TestConfig(app_env="test", database_url="postgres://localhost/partsiq", production_project_ref="prodref"))
    print("assert_disposable_environment: local/test OK")
