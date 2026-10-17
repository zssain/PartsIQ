"""F63 Metrics dashboard (owner: gateway; depends on 21, 23).

Wraps the prompt-23 operational metrics (app.metrics.get_metrics) for a dashboard: staff-only,
demo traffic excluded by default (so it never silently improves operational metrics), time
window honoured. Labelled-accuracy EVALUATION metrics are administrative — a plain reviewer
receives assignment-scoped operational counts only, so the evaluation fields are withheld for
non-admins. Accuracy is always reported WITH its denominator; a zero denominator is "unavailable"
(labelled_accuracy returns None) — never a fabricated percentage.

Pure over the injected MetricsRepo (assignment scoping + demo filtering live in the adapter).
"""
from __future__ import annotations

from app.metrics import MetricsRepo, get_metrics
from partsiq_common.contracts import ActorContext, Contract, MetricsQuery, MetricsView


class F63Request(Contract):
    query: MetricsQuery


class F63Result(Contract):
    metrics: MetricsView


def labelled_accuracy(view: MetricsView) -> float | None:
    """correct / evaluated, or None when the denominator is zero (shown 'unavailable')."""
    if view.evaluated_count <= 0:
        return None
    return view.correct_count / view.evaluated_count


async def metrics_dashboard(actor: ActorContext, request: F63Request, *, repo: MetricsRepo) -> F63Result:
    """Staff metrics for the dashboard; evaluation accuracy is admin-only."""
    metrics = await get_metrics(actor, request.query, repo=repo)  # staff-only + demo-excluded by default
    if "admin" not in actor.roles:
        # Reviewers get assignment-scoped operational counts only — not the administrative
        # labelled-accuracy evaluation metrics.
        metrics = metrics.model_copy(update={"evaluated_count": 0, "correct_count": 0})
    return F63Result(metrics=metrics)
