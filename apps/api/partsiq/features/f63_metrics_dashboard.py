"""F63 Metrics dashboard facade (helpers ``analytics.metrics`` / ``analytics.read_sync``).

Two staff/admin read surfaces over operational analytics:

  * ``metrics`` returns scoped operational metrics for a window via the real
    :func:`partsiq.analytics.service.get_metrics`, which is STAFF-ONLY (a customer with no staff
    role raises FORBIDDEN, surfaced as a 403) and EXCLUDES demo traffic by default (F04), including
    it only when ``query.include_demo`` is set. Median review time, nearest-rank p95 latency and
    the summed estimated AI cost come from measured samples; an empty sample yields ``None`` rather
    than a fabricated zero. The scoped PostgreSQL samples repository is injected and is BLOCKED
    offline, so a staff caller gets a clean 503 rather than a fabricated figure.
  * ``read_sync`` returns the analytics-sync status (last success, pending events, source,
    staleness) for an admin — read-only.

No metric is ever fabricated; the aggregation runs only over recorded evidence.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from partsiq.analytics.service import MetricsRepo, get_metrics
from partsiq.core.api_models import AnalyticsSyncView
from partsiq.core.contracts import ActorContext, MetricsQuery, MetricsView
from partsiq.core.dependencies import AppContainer
from partsiq.core.errors import PartsIQError
from partsiq.features._ops_ports import require_store


def require_admin(actor: ActorContext) -> None:
    """Refuse a non-admin caller with FORBIDDEN (403) for the admin-only sync read."""
    from partsiq.auth.actors import has_capability

    if not has_capability(actor, "analytics.read"):
        raise PartsIQError("FORBIDDEN", internal_detail="analytics sync is admin-only")


@runtime_checkable
class AnalyticsSyncSource(Protocol):
    """Admin analytics-sync read port."""

    async def read_sync(self, actor: ActorContext) -> AnalyticsSyncView: ...


async def metrics(
    actor: ActorContext,
    query: MetricsQuery,
    *,
    container: AppContainer,
    repo: MetricsRepo | None = None,
) -> MetricsView:
    """Return scoped operational metrics (staff-only; demos excluded by default, F04/F63/F64).

    The staff-only gate lives in the domain :func:`get_metrics` (a customer raises FORBIDDEN). The
    scoped samples repository is injected; it is unwired offline, so a staff caller gets a clean
    503 (the figures are never fabricated).
    """
    repo = repo or require_store(container, "metrics_repo")
    return await get_metrics(actor, query, repo=repo)


async def read_sync(
    actor: ActorContext,
    *,
    container: AppContainer,
    source: AnalyticsSyncSource | None = None,
) -> AnalyticsSyncView:
    """Return the analytics-sync status (admin-only; read-only)."""
    require_admin(actor)
    source = source or require_store(container, "analytics_sync")
    return await source.read_sync(actor)
