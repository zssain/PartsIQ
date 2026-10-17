"""Free-credit allowance accounting for structured-output calls (foundation 10).

Design rules (CONSTRAINTS rules 13, 14 and prompt 10 steps 8-11):
  * AI spends ONLY against an owner-confirmed free-credit allowance. There is NO paid
    fallback: ``CreditAllowance.paid_budget_usd`` is constrained ``le=0`` by the contract,
    and a non-zero paid budget is a hard block here as well (defence in depth), never a
    cap to spend up to.
  * An unknown model price BLOCKS the call — a price is never guessed.
  * An expired allowance BLOCKS the call.
  * An insufficient allowance BLOCKS the call.
  * Reservations are atomic: a worst-case cost is reserved BEFORE every external attempt
    so concurrent calls cannot collectively exceed the allowance.
  * A reservation stays reserved until it is reconciled. Only a demonstrably unused
    reservation is released; an uncertain outcome (e.g. an ambiguous timeout) keeps the
    reservation held against the cap (prompt 10 step 11).
  * A valid API key is never evidence of free credit; only a confirmed allowance is.

This ledger is local and authoritative; it is also the deterministic test double. Live
calls back it with Redis for cross-process caps, but the decision logic is identical.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from partsiq.core.contracts import AIRequest, BudgetReservation, CreditAllowance
from partsiq.core.errors import PartsIQError

_PRICES_PATH = Path(__file__).with_name("prices.json")
_MILLION = Decimal(1_000_000)


def load_prices(path: Path = _PRICES_PATH) -> dict:
    """Load the model price table (USD per 1M tokens) used only to estimate/cap spend."""
    return json.loads(path.read_text(encoding="utf-8"))


def estimate_cost_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    prices: dict | None = None,
) -> Decimal:
    """Estimate the USD cost of a call.

    Raise ``PartsIQError(CREDIT_UNAVAILABLE)`` if the model has no recorded price — an
    unpriced call must never run (CONSTRAINTS rule 13); the price is never guessed.
    """
    prices = prices if prices is not None else load_prices()
    model_prices = prices.get("models", {}).get(model)
    if model_prices is None:
        raise PartsIQError(
            "CREDIT_UNAVAILABLE", internal_detail=f"no price recorded for model {model!r}"
        )
    per_in = Decimal(str(model_prices["input"]))
    per_out = Decimal(str(model_prices["output"]))
    return (per_in * Decimal(input_tokens) + per_out * Decimal(output_tokens)) / _MILLION


def assert_allowance_callable(allowance: CreditAllowance, now: datetime) -> None:
    """Raise unless a live call may be attempted at all under this allowance.

    The contract already constrains ``paid_budget_usd`` to ``le=0``; this re-asserts it as
    defence in depth so a mis-constructed allowance cannot open a paid fallback.
    """
    if allowance.paid_budget_usd != 0:
        raise PartsIQError("CREDIT_UNAVAILABLE", internal_detail="paid budget must be zero")
    if allowance.amount_usd <= 0:
        raise PartsIQError("CREDIT_UNAVAILABLE", internal_detail="no confirmed allowance")
    expires = allowance.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if now >= expires:
        raise PartsIQError("CREDIT_UNAVAILABLE", internal_detail="allowance expired")


@dataclass
class InMemoryBudgetLedger:
    """Atomic allowance ledger.

    Thread-safe so concurrent reservations cannot collectively exceed the confirmed
    allowance. Reservations stay open (reserved against the cap) until explicitly settled
    or released.
    """

    allowance: CreditAllowance
    account_id: str = "default"
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _reserved_total: Decimal = field(default=Decimal(0), init=False)
    _consumed_total: Decimal = field(default=Decimal(0), init=False)
    _open: dict[UUID, Decimal] = field(default_factory=dict, init=False)

    def reserve(self, estimated_usd: Decimal, now: datetime) -> BudgetReservation:
        """Reserve ``estimated_usd`` against the allowance BEFORE an attempt.

        Raise before the committed + newly reserved spend could exceed the confirmed
        allowance. Blocks for a non-zero paid budget, no allowance or an expired allowance.
        """
        assert_allowance_callable(self.allowance, now)
        with self._lock:
            committed = self._reserved_total + self._consumed_total
            if committed + estimated_usd > self.allowance.amount_usd:
                raise PartsIQError(
                    "QUOTA_EXCEEDED", internal_detail="confirmed allowance insufficient"
                )
            reservation_id = uuid4()
            self._reserved_total += estimated_usd
            self._open[reservation_id] = estimated_usd
            return BudgetReservation(
                id=reservation_id, account_id=self.account_id, reserved_usd=estimated_usd
            )

    def settle(self, reservation: BudgetReservation, actual_usd: Decimal) -> None:
        """Replace an open reservation's estimate with the actual spend after a call.

        Settling converts a conservative worst-case hold into the measured cost. A
        reservation already closed (settled/released) is ignored so reconciliation is
        idempotent.
        """
        with self._lock:
            estimated = self._open.pop(reservation.id, None)
            if estimated is None:
                return
            self._reserved_total -= estimated
            self._consumed_total += actual_usd

    def release(self, reservation: BudgetReservation) -> None:
        """Release a DEMONSTRABLY unused reservation (the call never spent credit).

        Only call this when non-usage is proven (e.g. the budget gate itself failed, or a
        clean pre-dispatch error). On an uncertain outcome the reservation must stay held
        (prompt 10 step 11); do not call this to "tidy up" an ambiguous timeout.
        """
        with self._lock:
            estimated = self._open.pop(reservation.id, None)
            if estimated is None:
                return
            self._reserved_total -= estimated

    def snapshot(self) -> dict[str, str]:
        """Expose reserved/consumed/allowance (decimal strings) for metrics."""
        with self._lock:
            return {
                "reserved_usd": str(self._reserved_total),
                "consumed_usd": str(self._consumed_total),
                "allowance_usd": str(self.allowance.amount_usd),
                "open_reservations": str(len(self._open)),
            }


def reserve_for_request(
    ledger: InMemoryBudgetLedger,
    request: AIRequest,
    *,
    now: datetime,
    max_input_tokens: int,
    prices: dict | None = None,
) -> BudgetReservation:
    """Reserve the WORST-CASE cost for one attempt of ``request`` before the call.

    Uses ``max_input_tokens`` plus the request's hard ``max_output_tokens`` cap so a
    reservation can never under-reserve. An unknown price raises ``CREDIT_UNAVAILABLE``
    (never guessed); an expired or insufficient allowance also blocks. The returned
    reservation is held against the cap until the caller reconciles it — on an uncertain
    outcome the caller must NOT release it (prompt 10 step 11).
    """
    worst_case = estimate_cost_usd(
        request.model, max_input_tokens, request.max_output_tokens, prices
    )
    return ledger.reserve(worst_case, now)
