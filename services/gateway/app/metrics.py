"""Operational metrics (prompt 23 — F64).

Contract: ``async def get_metrics(actor: ActorContext, query: MetricsQuery) -> MetricsView``.

Staff-only. Demo enquiries are excluded by default (F04) unless explicitly included. Timings
are measured upstream with a monotonic clock (telemetry.Stage); here we aggregate the
persisted samples — median review time and p95 latency are computed from the raw samples, and
estimated AI cost is summed from recorded per-call costs. The metrics repository is injected
so the aggregation is testable offline.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol

from partsiq_common.contracts import ActorContext, MetricsQuery, MetricsView
from partsiq_common.errors import PartsIQError

_STAFF_ROLES = {"reviewer", "admin"}


@dataclass(frozen=True, slots=True)
class MetricsSamples:
    """Raw samples for a window (already filtered by include_demo in the repository query)."""

    enquiry_count: int = 0
    approved_count: int = 0
    clarification_count: int = 0
    evaluated_count: int = 0
    correct_count: int = 0
    review_seconds: list[float] = field(default_factory=list)
    latencies_ms: list[float] = field(default_factory=list)
    estimated_cost_usd: Decimal = Decimal(0)


class MetricsRepo(Protocol):
    async def samples(self, query: MetricsQuery) -> MetricsSamples: ...


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(0.95 * len(ordered)))  # nearest-rank p95
    return ordered[rank - 1]


async def get_metrics(actor: ActorContext, query: MetricsQuery, *, repo: MetricsRepo) -> MetricsView:
    if not _STAFF_ROLES.intersection(actor.roles):
        raise PartsIQError("FORBIDDEN", internal_detail="metrics are staff-only")
    samples = await repo.samples(query)  # repo honours query.include_demo (demos excluded by default)
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
