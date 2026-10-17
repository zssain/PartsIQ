"""Scoped operational metrics and the manually-confirmed credit allowance (foundation 23).

Two domain responsibilities, both ported from the characterized legacy code:

  * :func:`get_metrics` (``services/gateway/app/metrics.py``, F63/F64) — STAFF-ONLY. A customer
    (no staff role) is refused; the HTTP adapter maps the raised error to a 403/404 per the
    prompt (a staff-only resource is not disclosed to a customer). Demo traffic is EXCLUDED by
    default (F04) and included only when ``query.include_demo`` is set. The view reports median
    review time, the NEAREST-RANK p95 latency and the SUMMED estimated AI cost over the window.
    Live staff counts stay scoped PostgreSQL queries behind an injected repository, so the
    aggregation is deterministic and testable offline.
  * :func:`validate_allowance` / :func:`allowance_view` (``tools/credit_allowance.py``, F64) —
    an allowance is an EXPLICIT owner confirmation (amount, expiry, acknowledged zero paid
    budget), NEVER inferred from the presence of an API key (CONSTRAINTS 13, 14). A non-zero
    paid budget, a non-positive amount, or an already-expired credit is a hard block.

No provider or database side effects at import time; the metrics repository is injected.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol

from partsiq.core.api_models import AllowanceSet, AllowanceView
from partsiq.core.contracts import ActorContext, CreditAllowance, MetricsQuery, MetricsView
from partsiq.core.errors import PartsIQError

# Staff roles that may read operational metrics. A customer carries no staff role.
_STAFF_ROLES: frozenset[str] = frozenset({"reviewer", "catalogue_admin", "admin"})


@dataclass(frozen=True, slots=True)
class MetricsSamples:
    """Raw samples for a window (already filtered by ``include_demo`` in the repository query).

    ``review_seconds`` and ``latencies_ms`` are the raw per-event samples; the service computes
    the median and nearest-rank p95 from them. ``estimated_cost_usd`` is the window's summed AI
    cost (CONSTRAINTS 18: a cost claim is always tied to recorded, measured evidence).
    """

    enquiry_count: int = 0
    approved_count: int = 0
    clarification_count: int = 0
    evaluated_count: int = 0
    correct_count: int = 0
    review_seconds: list[float] = field(default_factory=list)
    latencies_ms: list[float] = field(default_factory=list)
    estimated_cost_usd: Decimal = Decimal(0)


class MetricsRepo(Protocol):
    """Scoped PostgreSQL metrics source. Honours ``query.include_demo`` and reviewer scope."""

    async def samples(self, actor: ActorContext, query: MetricsQuery) -> MetricsSamples: ...


def _median(values: list[float]) -> float | None:
    """Median of a sample, or ``None`` for an empty sample (never a fabricated zero)."""
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2


def _p95(values: list[float]) -> float | None:
    """Nearest-rank p95: the value at ceil(0.95 * n). ``None`` for an empty sample."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(0.95 * len(ordered)))  # nearest-rank p95
    return float(ordered[rank - 1])


async def get_metrics(
    actor: ActorContext, query: MetricsQuery, *, repo: MetricsRepo
) -> MetricsView:
    """Return scoped operational metrics for ``actor`` over ``query``'s window (F63/F64).

    STAFF-ONLY: a customer (no staff role) raises ``FORBIDDEN`` — the route adapter surfaces
    that per the prompt's access rules and never discloses the figures. The repository applies
    ``query.include_demo`` (demos excluded by default, F04) and the reviewer's assignment scope.
    Median review seconds, nearest-rank p95 latency and the SUMMED estimated cost are computed
    from the raw samples; an empty sample yields ``None`` rather than a fabricated value.
    """
    if not _STAFF_ROLES.intersection(actor.roles):
        raise PartsIQError("FORBIDDEN", internal_detail="operational metrics are staff-only")
    samples = await repo.samples(actor, query)
    return MetricsView(
        enquiry_count=samples.enquiry_count,
        approved_count=samples.approved_count,
        clarification_count=samples.clarification_count,
        evaluated_count=samples.evaluated_count,
        correct_count=samples.correct_count,
        median_review_seconds=_median(samples.review_seconds),
        p95_latency_ms=_p95(samples.latencies_ms),
        estimated_cost_usd=samples.estimated_cost_usd,
    )


def validate_allowance(
    amount: Decimal,
    expires_at: datetime,
    paid_budget: Decimal,
    *,
    now: datetime | None = None,
) -> CreditAllowance:
    """Validate a MANUALLY-CONFIRMED free-credit allowance (CONSTRAINTS 13, 14; F64).

    The allowance is an explicit owner confirmation — amount, expiry and an acknowledged zero
    paid budget — and is NEVER inferred from the presence of an API key. Each of a non-zero paid
    budget, a non-positive amount, and an already-expired credit is a HARD block (the live call
    path stays disabled until a valid allowance is configured). Returns the typed
    :class:`CreditAllowance`, whose own ``paid_budget_usd in [0, 0]`` constraint re-checks the
    no-paid-fallback rule as defence in depth.
    """
    now = now or datetime.now(UTC)
    if paid_budget != 0:
        raise PartsIQError(
            "CREDIT_UNAVAILABLE",
            internal_detail="paid budget must be zero (no paid fallback)",
        )
    if amount <= 0:
        raise PartsIQError(
            "CREDIT_UNAVAILABLE", internal_detail="allowance amount must be positive"
        )
    expires = expires_at if expires_at.tzinfo is not None else expires_at.replace(tzinfo=UTC)
    if expires <= now:
        raise PartsIQError("CREDIT_UNAVAILABLE", internal_detail="allowance has expired")
    return CreditAllowance(amount_usd=amount, expires_at=expires_at, paid_budget_usd=Decimal(0))


def allowance_view(
    allowance: CreditAllowance | None,
    *,
    consumed_usd: Decimal,
    reserved_usd: Decimal,
    model: str | None,
    now: datetime | None = None,
) -> AllowanceView:
    """Expose the consumed/reserved allowance for the dashboard (F64).

    ``enabled`` is TRUE only when a confirmed allowance exists AND has not expired — it is never
    implied by an API key. ``confirmed_usd`` is 0 and ``enabled`` False when no allowance is set.
    """
    now = now or datetime.now(UTC)
    if allowance is None:
        return AllowanceView(
            enabled=False,
            confirmed_usd=Decimal(0),
            consumed_usd=consumed_usd,
            reserved_usd=reserved_usd,
            expires_at=None,
            model=model,
        )
    expires = (
        allowance.expires_at
        if allowance.expires_at.tzinfo is not None
        else allowance.expires_at.replace(tzinfo=UTC)
    )
    enabled = allowance.amount_usd > 0 and allowance.paid_budget_usd == 0 and expires > now
    return AllowanceView(
        enabled=enabled,
        confirmed_usd=allowance.amount_usd,
        consumed_usd=consumed_usd,
        reserved_usd=reserved_usd,
        expires_at=allowance.expires_at,
        model=model,
    )


def allowance_from_set(request: AllowanceSet, *, now: datetime | None = None) -> CreditAllowance:
    """Build a validated :class:`CreditAllowance` from an :class:`AllowanceSet` request.

    An owner confirming an allowance supplies an explicit amount and expiry (and implicitly a
    zero paid budget); this routes through :func:`validate_allowance` so the same hard blocks
    apply — an allowance can never be established with a non-positive amount or a past expiry.
    """
    return validate_allowance(
        request.confirmed_usd, request.expires_at, Decimal(0), now=now
    )
