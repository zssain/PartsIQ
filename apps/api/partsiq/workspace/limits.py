"""Server-enforced run limits and the per-run AI budget (ADR 0002, docs/RUN_LIMITS.md).

All numbers come from :class:`~partsiq.core.settings.Settings` (one place, configurable by env);
components read them from :class:`RunLimits` rather than scattering literals. A limit breach
stops further dispatch, preserves completed work and records the blocked reason; it never
fabricates a successful response.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from partsiq.ai.budget import InMemoryBudgetLedger, estimate_cost_usd
from partsiq.core.contracts import CreditAllowance
from partsiq.core.errors import PartsIQError


@dataclass(frozen=True)
class RunLimits:
    max_agent_turns: int
    max_tool_calls: int
    max_output_tokens_per_turn: int
    max_output_tokens: int
    max_usd: Decimal
    max_wall_seconds: int
    max_retries: int
    max_concurrent_per_scope: int
    max_message_bytes: int
    max_instruction_chars: int
    max_upload_bytes: int
    max_image_pixels: int

    @classmethod
    def from_settings(cls, settings: Any) -> "RunLimits":
        return cls(
            max_agent_turns=settings.run_max_agent_turns,
            max_tool_calls=settings.run_max_tool_calls,
            max_output_tokens_per_turn=settings.run_max_output_tokens_per_turn,
            max_output_tokens=settings.run_max_output_tokens,
            max_usd=Decimal(settings.run_max_usd),
            max_wall_seconds=settings.run_max_wall_seconds,
            max_retries=settings.run_max_retries,
            max_concurrent_per_scope=settings.run_max_concurrent_per_scope,
            max_message_bytes=settings.run_max_message_bytes,
            max_instruction_chars=settings.run_max_instruction_chars,
            max_upload_bytes=settings.max_upload_bytes,
            max_image_pixels=settings.max_image_pixels,
        )

    def as_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["max_usd"] = str(self.max_usd)
        return out


class LimitReached(Exception):
    """Raised inside a run step when a configured limit stops further dispatch."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


def global_ledger(settings: Any) -> InMemoryBudgetLedger | None:
    """The process-wide confirmed-allowance ledger, or None when live AI is not configured."""
    if settings.ai_mode != "live" or settings.ai_confirmed_allowance_usd <= 0:
        return None
    expires = settings._parse_utc(settings.ai_allowance_expires_at)
    if expires is None:
        return None
    return InMemoryBudgetLedger(
        allowance=CreditAllowance(
            amount_usd=Decimal(settings.ai_confirmed_allowance_usd),
            expires_at=expires,
            paid_budget_usd=Decimal("0"),
        ),
        account_id="openai-confirmed-allowance",
    )


class RunBudget:
    """Per-run cap layered over the global allowance ledger.

    ``reserve`` checks the run's own output-token and USD caps BEFORE reserving the worst case in
    the global ledger, so one run cannot drain the shared allowance and an exhausted allowance
    blocks rather than spilling into paid usage.
    """

    def __init__(self, *, ledger: Any, model: str, limits: RunLimits, usage: Any) -> None:
        self._ledger = ledger
        self._model = model
        self._limits = limits
        self._usage = usage  # RunUsage (mutated as calls settle)

    async def reserve(self, stage: str, max_output_tokens: int) -> Any:
        if self._ledger is None:
            raise PartsIQError("CREDIT_UNAVAILABLE", internal_detail="no confirmed allowance ledger")
        cap = min(max_output_tokens, self._limits.max_output_tokens_per_turn * 2)
        if self._usage.output_tokens + cap > self._limits.max_output_tokens:
            raise LimitReached("output_tokens", "The run reached its output-token limit.")
        worst = estimate_cost_usd(self._model, 4000, cap)
        if self._usage.estimated_usd + worst > self._limits.max_usd:
            raise LimitReached("run_allowance", "The run reached its share of the AI allowance.")
        try:
            if isinstance(self._ledger, InMemoryBudgetLedger):
                return self._ledger.reserve(worst, datetime.now(timezone.utc))
            # Durable ledger (database mode): one atomic statement across all processes.
            return await self._ledger.reserve(worst, datetime.now(timezone.utc), model=self._model, stage=stage)
        except PartsIQError as exc:
            raise LimitReached("allowance_exhausted", "The confirmed AI allowance is exhausted or expired.") from exc

    async def settle(self, reservation: Any, input_tokens: int, output_tokens: int) -> Decimal:
        actual = estimate_cost_usd(self._model, input_tokens, output_tokens)
        if isinstance(self._ledger, InMemoryBudgetLedger):
            self._ledger.settle(reservation, actual)
        elif self._ledger is not None:
            await self._ledger.settle(reservation, actual, input_tokens=input_tokens, output_tokens=output_tokens)
        self._usage.input_tokens += input_tokens
        self._usage.output_tokens += output_tokens
        self._usage.estimated_usd += actual
        return actual
