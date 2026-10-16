"""Shared fixtures for database integration tests.

These tests require a DISPOSABLE local Supabase/Postgres (never production). When no
reachable DATABASE_URL is configured, every dependent test is SKIPPED, so the suite is
honest about what actually ran (AGENTS.md rule 7). The production denylist
(PRODUCTION_PROJECT_REF) is enforced before any connection is opened.
"""
from __future__ import annotations

import os

import pytest

from tools.verify_env import _looks_like_production


def _disposable_dsn() -> str | None:
    dsn = os.environ.get("DATABASE_URL") or os.environ.get("MIGRATION_DATABASE_URL")
    if not dsn:
        return None
    if _looks_like_production(dsn, os.environ.get("PRODUCTION_PROJECT_REF")):
        pytest.exit("refusing to run integration tests against a production database", returncode=2)
    if (os.environ.get("APP_ENV") or "test").lower() == "production":
        pytest.exit("APP_ENV=production: refusing integration tests", returncode=2)
    return dsn


@pytest.fixture(scope="session")
def database_url() -> str:
    dsn = _disposable_dsn()
    if dsn is None:
        pytest.skip("no disposable DATABASE_URL configured; integration tests skipped")
    return dsn


@pytest.fixture()
async def actor_pool(database_url: str):
    """A psycopg pool bound to a restricted service login, reused across actors.

    Proves two different verified actors can share one pooled connection without
    leaking each other's transaction-local app.actor_id (CONSTRAINTS.md rule 11).
    """
    from psycopg_pool import AsyncConnectionPool

    pool = AsyncConnectionPool(conninfo=database_url, max_size=2, open=False)
    await pool.open()
    try:
        yield pool
    finally:
        await pool.close()
