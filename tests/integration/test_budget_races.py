"""Budget reservation races (prompt 22 — F64) against a DISPOSABLE migrated database.

Drives the production :class:`partsiq.ai.ledger_pg.PostgresBudgetLedger` from many concurrent
connections: worst-case reservations can never collectively exceed the confirmed cap, settled
spend survives a fresh ledger instance (restart), an uncertain call keeps its hold, and a lowered
cap that would forget recorded spend is refused. SKIPPED without a disposable DATABASE_URL.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest


async def _pool(database_url: str):
    import asyncpg

    return await asyncpg.create_pool(database_url, min_size=2, max_size=12, statement_cache_size=0)


def _allowance(cap: str):
    from partsiq.core.contracts import CreditAllowance

    return CreditAllowance(amount_usd=Decimal(cap), expires_at=datetime.now(UTC) + timedelta(days=1), paid_budget_usd=Decimal("0"))


@pytest.mark.asyncio
async def test_concurrent_reservations_cannot_exceed_cap(database_url):
    from partsiq.ai.ledger_pg import PostgresBudgetLedger
    from partsiq.core.errors import PartsIQError

    pool = await _pool(database_url)
    try:
        ledger = PostgresBudgetLedger(pool, _allowance("1.00"), account_id=f"race-{uuid4().hex[:8]}")
        await ledger.ensure()

        async def attempt():
            try:
                return await ledger.reserve(Decimal("0.03"), datetime.now(UTC), model="gpt-4o-mini", stage="race")
            except PartsIQError as exc:
                assert exc.code == "QUOTA_EXCEEDED"
                return None

        results = await asyncio.gather(*(attempt() for _ in range(60)))
        held = [r for r in results if r is not None]
        assert len(held) == 33  # floor(1.00 / 0.03): never one more
        snap = await ledger.refresh()
        assert Decimal(snap["reserved_usd"]) == Decimal("0.99")

        # Settle some, release one proven-unused hold, keep the rest (uncertain) held.
        for r in held[:10]:
            await ledger.settle(r, Decimal("0.01"), input_tokens=100, output_tokens=20)
        await ledger.release(held[10])
        await ledger.settle(held[0], Decimal("0.5"))  # a second settle is ignored (idempotent)

        # A restart: a NEW ledger instance reads the same durable totals.
        again = PostgresBudgetLedger(pool, _allowance("1.00"), account_id=ledger.account_id)
        await again.ensure()
        snap = again.snapshot()
        assert Decimal(snap["consumed_usd"]) == Decimal("0.10")
        assert Decimal(snap["reserved_usd"]) == Decimal("0.66")  # 22 uncertain holds stay reserved
        assert snap["open_reservations"] == "22"

        # Lowering the cap below recorded spend is refused, not silently "fitted".
        import asyncpg

        with pytest.raises(asyncpg.CheckViolationError):
            await PostgresBudgetLedger(pool, _allowance("0.50"), account_id=ledger.account_id).ensure()
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_expired_allowance_blocks_before_any_reservation(database_url):
    from partsiq.ai.ledger_pg import PostgresBudgetLedger
    from partsiq.core.errors import PartsIQError

    pool = await _pool(database_url)
    try:
        ledger = PostgresBudgetLedger(pool, _allowance("1.00"), account_id=f"exp-{uuid4().hex[:8]}")
        await ledger.ensure()
        with pytest.raises(PartsIQError):
            await ledger.reserve(Decimal("0.01"), datetime.now(UTC) + timedelta(days=2))
        assert (await ledger.refresh())["reserved_usd"] in ("0", "0E-8", "0.00000000")
    finally:
        await pool.close()
