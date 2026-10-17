"""Manually-confirmed free-credit allowance (prompt 23 — F64, ADR-015).

Contract: ``def validate_allowance(amount: Decimal, expires_at: datetime, paid_budget: Decimal) -> CreditAllowance``.

An allowance is an explicit owner confirmation — amount, expiry and an acknowledged zero
paid budget — NEVER inferred from the presence of an API key. A non-zero paid budget, a
non-positive amount, or an already-expired credit is a hard error; the call path stays
disabled by default until a valid allowance is configured.
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from partsiq_common.contracts import CreditAllowance
from partsiq_common.errors import PartsIQError


def validate_allowance(
    amount: Decimal,
    expires_at: datetime,
    paid_budget: Decimal,
    *,
    now: datetime | None = None,
) -> CreditAllowance:
    now = now or datetime.now(UTC)
    if paid_budget != 0:
        raise PartsIQError("CREDIT_UNAVAILABLE", internal_detail="paid budget must be zero (no paid fallback)")
    if amount <= 0:
        raise PartsIQError("CREDIT_UNAVAILABLE", internal_detail="allowance amount must be positive")
    if expires_at <= now:
        raise PartsIQError("CREDIT_UNAVAILABLE", internal_detail="allowance has expired")
    # The contract itself enforces paid_budget_usd in [0, 0]; constructing it re-checks that.
    return CreditAllowance(amount_usd=amount, expires_at=expires_at, paid_budget_usd=Decimal(0))
