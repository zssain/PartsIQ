"""Free-credit allowance accounting for OpenAI calls.

Design rules (ADR-015, F64):
  * AI is OFF unless an owner-confirmed allowance is explicitly configured.
  * The paid budget must stay zero — there is no automatic paid fallback. A non-zero
    paid budget is a hard error, not a cap to spend up to.
  * An unknown model price blocks the call (we never guess a price).
  * An expired credit blocks the call.
  * Reservations are atomic so concurrent calls cannot collectively exceed a cap.
  * A valid API key never implies free credit; only configuration does.

This module is local and authoritative: a tracing/exporter outage never changes
these decisions (F67). The in-memory ledger here is the reference implementation and
the test double; the worker/orchestrator back it with Redis for cross-process caps.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from partsiq_common.contracts import BudgetReservation
from partsiq_common.errors import PartsIQError

_PRICES_PATH = Path(__file__).with_name("prices.json")
_MILLION = Decimal(1_000_000)


class BudgetError(PartsIQError):
    """Raised when a call may not proceed under the current allowance."""


def load_prices(path: Path = _PRICES_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def estimate_cost_usd(
    model: str, input_tokens: int, output_tokens: int, prices: dict | None = None
) -> Decimal:
    """Estimate USD cost for a call. Raise BudgetError(CREDIT_UNAVAILABLE) if the model
    has no recorded price — an unpriced call must not run (F64)."""
    prices = prices or load_prices()
    model_prices = prices.get("models", {}).get(model)
    if model_prices is None:
        raise BudgetError("CREDIT_UNAVAILABLE", internal_detail=f"no price for model {model!r}")
    per_in = Decimal(str(model_prices["input"]))
    per_out = Decimal(str(model_prices["output"]))
    return (per_in * Decimal(input_tokens) + per_out * Decimal(output_tokens)) / _MILLION


@dataclass(frozen=True, slots=True)
class AllowancePolicy:
    """Owner-confirmed allowance, normally loaded from the environment."""

    enabled: bool
    free_credit_usd: Decimal
    expires_at: datetime | None
    paid_budget_usd: Decimal
    daily_allowance_usd: Decimal
    session_allowance_usd: Decimal

    @classmethod
    def from_env(cls, env: dict[str, str]) -> "AllowancePolicy":
        def dec(name: str) -> Decimal:
            return Decimal(str(env.get(name, "0") or "0"))

        expires_raw = env.get("AI_CREDIT_EXPIRES_AT") or ""
        expires_at: datetime | None = None
        if expires_raw.strip():
            expires_at = datetime.fromisoformat(expires_raw.strip().replace("Z", "+00:00"))
        return cls(
            enabled=(env.get("AI_ENABLED", "false").strip().lower() == "true"),
            free_credit_usd=dec("AI_FREE_CREDIT_USD"),
            expires_at=expires_at,
            paid_budget_usd=dec("AI_PAID_BUDGET_USD"),
            daily_allowance_usd=dec("AI_DAILY_ALLOWANCE_USD"),
            session_allowance_usd=dec("AI_SESSION_ALLOWANCE_USD"),
        )

    def assert_callable(self, now: datetime) -> None:
        """Raise unless a call may be attempted at all under this policy."""
        if self.paid_budget_usd != 0:
            raise BudgetError("CREDIT_UNAVAILABLE", internal_detail="paid budget must be zero")
        if not self.enabled:
            raise BudgetError("CREDIT_UNAVAILABLE", internal_detail="AI disabled")
        if self.expires_at is None:
            raise BudgetError("CREDIT_UNAVAILABLE", internal_detail="no credit expiry configured")
        if now >= self.expires_at:
            raise BudgetError("CREDIT_UNAVAILABLE", internal_detail="credit expired")
        if self.free_credit_usd <= 0:
            raise BudgetError("CREDIT_UNAVAILABLE", internal_detail="no free credit configured")


def _day_key(now: datetime) -> str:
    return now.astimezone(timezone.utc).date().isoformat()


@dataclass
class InMemoryBudgetLedger:
    """Atomic allowance ledger. Thread-safe so concurrent reservations cannot exceed a cap."""

    policy: AllowancePolicy
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _reserved_total: Decimal = field(default=Decimal(0), init=False)
    _consumed_total: Decimal = field(default=Decimal(0), init=False)
    _daily: dict[str, Decimal] = field(default_factory=dict, init=False)
    _session: dict[str, Decimal] = field(default_factory=dict, init=False)
    _open: dict[UUID, tuple[str, str | None, Decimal]] = field(default_factory=dict, init=False)

    def reserve(
        self,
        account_id: str,
        estimated_usd: Decimal,
        now: datetime,
        session_id: str | None = None,
    ) -> BudgetReservation:
        """Reserve estimated spend. Raise before exceeding any cap. Call before each attempt."""
        self.policy.assert_callable(now)
        day = _day_key(now)
        with self._lock:
            committed = self._reserved_total + self._consumed_total
            if committed + estimated_usd > self.policy.free_credit_usd:
                raise BudgetError("QUOTA_EXCEEDED", internal_detail="free credit exhausted")
            day_used = self._daily.get(day, Decimal(0))
            if day_used + estimated_usd > self.policy.daily_allowance_usd:
                raise BudgetError("QUOTA_EXCEEDED", internal_detail="daily allowance exhausted")
            if session_id is not None:
                sess_used = self._session.get(session_id, Decimal(0))
                if sess_used + estimated_usd > self.policy.session_allowance_usd:
                    raise BudgetError("QUOTA_EXCEEDED", internal_detail="session allowance exhausted")
                self._session[session_id] = sess_used + estimated_usd
            self._daily[day] = day_used + estimated_usd
            self._reserved_total += estimated_usd
            reservation_id = uuid4()
            self._open[reservation_id] = (account_id, session_id, estimated_usd)
            return BudgetReservation(id=reservation_id, account_id=account_id, reserved_usd=estimated_usd)

    def settle(self, reservation: BudgetReservation, actual_usd: Decimal, now: datetime) -> None:
        """Replace a reservation's estimate with actual spend after the call returns."""
        with self._lock:
            opened = self._open.pop(reservation.id, None)
            if opened is None:
                return
            _, session_id, estimated = opened
            delta = actual_usd - estimated
            self._reserved_total -= estimated
            self._consumed_total += actual_usd
            day = _day_key(now)
            self._daily[day] = self._daily.get(day, Decimal(0)) + delta
            if session_id is not None:
                self._session[session_id] = self._session.get(session_id, Decimal(0)) + delta

    def release(self, reservation: BudgetReservation, now: datetime) -> None:
        """Release an unused reservation (e.g. the call failed before spending)."""
        with self._lock:
            opened = self._open.pop(reservation.id, None)
            if opened is None:
                return
            _, session_id, estimated = opened
            self._reserved_total -= estimated
            day = _day_key(now)
            self._daily[day] = self._daily.get(day, Decimal(0)) - estimated
            if session_id is not None:
                self._session[session_id] = self._session.get(session_id, Decimal(0)) - estimated

    def snapshot(self) -> dict[str, str]:
        """Expose consumed/reserved allowance (decimal strings) for metrics (F64)."""
        with self._lock:
            return {
                "reserved_usd": str(self._reserved_total),
                "consumed_usd": str(self._consumed_total),
                "free_credit_usd": str(self.policy.free_credit_usd),
            }
