"""Durable confirmed-allowance ledger over ``ai_budget_accounts`` / ``ai_usage`` (database mode).

The in-memory ledger forgets spend on restart, which could let usage exceed the owner's
confirmed allowance. This ledger makes every reservation one atomic statement:

    UPDATE ai_budget_accounts SET reserved_usd = reserved_usd + $estimate
     WHERE id = $account AND enabled AND expires_at > now()
       AND reserved_usd + consumed_usd + $estimate <= cap_usd

so concurrent reservations (any number of API/worker processes) can never collectively exceed
the cap, and the table's own CHECK (reserved + consumed <= cap) backs it up. Each reservation
is an ``ai_usage`` row; an uncertain outcome keeps its hold (never auto-released).
"""
from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from partsiq.ai.budget import assert_allowance_callable
from partsiq.core.contracts import BudgetReservation, CreditAllowance
from partsiq.core.errors import PartsIQError

logger = logging.getLogger("partsiq.ai.ledger")


class PostgresBudgetLedger:
    def __init__(self, pool: Any, allowance: CreditAllowance, *, account_id: str = "openai-confirmed-allowance") -> None:
        self.pool = pool
        self.allowance = allowance
        self.account_id = account_id
        self._snap = {"reserved_usd": "0", "consumed_usd": "0", "allowance_usd": str(allowance.amount_usd), "open_reservations": "0"}

    async def ensure(self) -> None:
        """Create or update the account with the owner's confirmed cap and expiry.

        Lowering the cap below what is already reserved + consumed violates the table CHECK and
        fails startup: spend already recorded is never forgotten to fit a smaller cap.
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO ai_budget_accounts(id, cap_usd, expires_at, enabled) VALUES ($1, $2, $3, true)
                   ON CONFLICT (id) DO UPDATE SET cap_usd = EXCLUDED.cap_usd, expires_at = EXCLUDED.expires_at, enabled = true""",
                self.account_id, self.allowance.amount_usd, self.allowance.expires_at,
            )
        await self.refresh()

    async def reserve(self, estimated_usd: Decimal, now: datetime, *, model: str = "", stage: str = "run", enquiry_id: UUID | None = None) -> BudgetReservation:
        assert_allowance_callable(self.allowance, now)
        reservation_id = uuid4()
        async with self.pool.acquire() as conn, conn.transaction():
            held = await conn.fetchval(
                """UPDATE ai_budget_accounts SET reserved_usd = reserved_usd + $2
                    WHERE id = $1 AND enabled AND expires_at > now() AND reserved_usd + consumed_usd + $2 <= cap_usd
                    RETURNING 1""",
                self.account_id, estimated_usd,
            )
            if not held:
                raise PartsIQError("QUOTA_EXCEEDED", internal_detail="confirmed allowance insufficient")
            await conn.execute(
                "INSERT INTO ai_usage(id, enquiry_id, request_key, budget_account_id, model, stage, status, reserved_usd) VALUES ($1, $2, $1, $3, $4, $5, 'reserved', $6)",
                reservation_id, enquiry_id, self.account_id, model or "unknown", stage[:40], estimated_usd,
            )
        await self.refresh()
        return BudgetReservation(id=reservation_id, account_id=self.account_id, reserved_usd=estimated_usd)

    async def settle(self, reservation: BudgetReservation, actual_usd: Decimal, *, input_tokens: int | None = None, output_tokens: int | None = None) -> None:
        """Replace the hold with the measured cost (idempotent: a closed reservation is ignored)."""
        async with self.pool.acquire() as conn, conn.transaction():
            held = await conn.fetchval(
                "UPDATE ai_usage SET status='completed', actual_usd=$2, input_tokens=$3, output_tokens=$4 WHERE request_key=$1 AND status IN ('reserved','uncertain') RETURNING reserved_usd",
                reservation.id, actual_usd, input_tokens, output_tokens,
            )
            if held is None:
                return
            # Saturate rather than under-record: if the measured cost exceeded the worst-case hold,
            # the account is filled to its cap (further calls block) instead of the spend being lost.
            await conn.execute(
                """UPDATE ai_budget_accounts SET reserved_usd = reserved_usd - $2,
                          consumed_usd = least(consumed_usd + $3, cap_usd - (reserved_usd - $2)) WHERE id = $1""",
                self.account_id, held, actual_usd,
            )
            if actual_usd > held:
                logger.warning("ai spend exceeded its reservation; allowance saturated")
        await self.refresh()

    async def release(self, reservation: BudgetReservation) -> None:
        """Release a DEMONSTRABLY unused reservation (never for an ambiguous outcome)."""
        async with self.pool.acquire() as conn, conn.transaction():
            held = await conn.fetchval("UPDATE ai_usage SET status='released', actual_usd=0 WHERE request_key=$1 AND status='reserved' RETURNING reserved_usd", reservation.id)
            if held is not None:
                await conn.execute("UPDATE ai_budget_accounts SET reserved_usd = reserved_usd - $2 WHERE id = $1", self.account_id, held)
        await self.refresh()

    async def refresh(self) -> dict[str, str]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT cap_usd, reserved_usd, consumed_usd FROM ai_budget_accounts WHERE id=$1", self.account_id)
            open_count = await conn.fetchval("SELECT count(*) FROM ai_usage WHERE budget_account_id=$1 AND status='reserved'", self.account_id)
        if row is not None:
            self._snap = {"reserved_usd": str(row["reserved_usd"]), "consumed_usd": str(row["consumed_usd"]), "allowance_usd": str(row["cap_usd"]), "open_reservations": str(open_count)}
        return dict(self._snap)

    def snapshot(self) -> dict[str, str]:
        """Last values read from PostgreSQL (refreshed after every reserve/settle/release)."""
        return dict(self._snap)


__all__ = ["PostgresBudgetLedger"]
