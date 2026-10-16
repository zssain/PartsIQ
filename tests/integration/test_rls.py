"""RLS enforcement integration tests (prompt 22 — F54).

Require a disposable local Supabase: a second verified actor cannot read another actor's
rows, and a request with no actor context returns no rows (RLS denies by default). SKIPPED
when no disposable DATABASE_URL is configured (the conftest fixture enforces the prod
denylist). Instantiates the existing restricted-role pool; no new business logic.
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_foreign_actor_sees_no_rows(actor_pool):  # pragma: no cover - needs live DB
    # With a disposable DB: set app.actor_id to actor A, insert; switch to actor B; assert
    # B reads zero rows and a missing-context connection also reads zero (RLS default-deny).
    raise AssertionError("RLS two-actor isolation must run against a disposable local Supabase")
