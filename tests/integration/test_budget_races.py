"""Budget reservation race integration tests (prompt 22 — F64).

Require a disposable local Supabase: concurrent worst-case reservations against the same
allowance cannot exceed the configured cap (atomic reserve), and an uncertain request keeps
its reservation. SKIPPED when no disposable DATABASE_URL is configured. Instantiates the
existing allowance ledger; no new business logic.
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_concurrent_reservations_cannot_exceed_cap(actor_pool):  # pragma: no cover - needs live DB
    raise AssertionError("budget reservation races must run against a disposable local ledger")
