"""F63 HTTP adapters (metrics dashboard):

* GET /v1/staff/metrics        (200) scoped operational metrics for a window (staff-only)
* GET /v1/admin/analytics/sync (200) analytics-sync status (admin-only)

``metrics`` validates the ``MetricsQuery`` fields (start/end/include_demo) as QUERY parameters;
demos are excluded unless ``include_demo`` is set (F04), and a customer with no staff role is
refused (403) by the domain gate. Delegates to the ``f63_metrics_dashboard`` facade, which surfaces
a clean 503 offline.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from partsiq.core.api_models import AnalyticsSyncView
from partsiq.core.contracts import ActorContext, MetricsQuery, MetricsView
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f63_metrics_dashboard as facade

router = APIRouter(tags=["staff"])


@router.get(
    "/staff/metrics",
    response_model=MetricsView,
    status_code=200,
    operation_id="f63_metrics",
    summary="Read scoped operational metrics for a window (staff-only; demos excluded by default)",
)
async def metrics(
    start: datetime = Query(...),
    end: datetime = Query(...),
    include_demo: bool = Query(default=False),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> MetricsView:
    query = MetricsQuery(start=start, end=end, include_demo=include_demo)
    return await facade.metrics(actor, query, container=container)


@router.get(
    "/admin/analytics/sync",
    response_model=AnalyticsSyncView,
    status_code=200,
    operation_id="f63_read_sync",
    summary="Read the analytics-sync status (admin-only)",
)
async def read_sync(
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> AnalyticsSyncView:
    return await facade.read_sync(actor, container=container)
