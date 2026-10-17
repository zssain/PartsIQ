"""F63 Metrics dashboard — staff-only, admin-gated accuracy, denominators, demo separation.

Admin sees labelled-accuracy evaluation metrics; a reviewer gets operational counts only (eval
withheld). Accuracy is reported with its denominator; a zero denominator is unavailable (None),
never a fabricated percentage. Demo traffic is excluded by default so it never silently improves
operational metrics.
"""
from __future__ import annotations

import unittest
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from app.features.f63_metrics_dashboard import F63Request, labelled_accuracy, metrics_dashboard
from app.metrics import MetricsSamples
from partsiq_common.contracts import ActorContext, MetricsQuery
from partsiq_common.errors import PartsIQError

WINDOW = MetricsQuery(start=datetime(2026, 10, 1, tzinfo=UTC), end=datetime(2026, 10, 17, tzinfo=UTC))


def _admin():
    return ActorContext(user_id=uuid4(), request_id=uuid4(), roles=["admin"])


def _reviewer():
    return ActorContext(user_id=uuid4(), request_id=uuid4(), roles=["reviewer"])


class FakeMetricsRepo:
    def __init__(self, real, demo=None, *, raises=None):
        self._real = real
        self._demo = demo
        self._raises = raises
        self.last_query = None

    async def samples(self, query):
        if self._raises is not None:
            raise self._raises
        self.last_query = query
        if query.include_demo and self._demo is not None:
            return self._demo
        return self._real


def _samples(**kw):
    base = dict(enquiry_count=10, approved_count=6, clarification_count=3,
                evaluated_count=8, correct_count=7, review_seconds=[30.0, 60.0], latencies_ms=[100.0],
                estimated_cost_usd=Decimal("0.05"))
    base.update(kw)
    return MetricsSamples(**base)


class MetricsDashboard(unittest.IsolatedAsyncioTestCase):
    async def test_admin_sees_evaluation_metrics(self):
        repo = FakeMetricsRepo(_samples())
        result = await metrics_dashboard(_admin(), F63Request(query=WINDOW), repo=repo)
        self.assertEqual(result.metrics.evaluated_count, 8)
        self.assertEqual(result.metrics.correct_count, 7)
        self.assertAlmostEqual(labelled_accuracy(result.metrics), 7 / 8)

    async def test_reviewer_eval_metrics_withheld(self):
        repo = FakeMetricsRepo(_samples())
        result = await metrics_dashboard(_reviewer(), F63Request(query=WINDOW), repo=repo)
        self.assertEqual(result.metrics.evaluated_count, 0)
        self.assertEqual(result.metrics.correct_count, 0)
        self.assertIsNone(labelled_accuracy(result.metrics))  # unavailable, not fabricated
        self.assertEqual(result.metrics.enquiry_count, 10)  # operational counts still shown

    async def test_zero_denominator_is_unavailable(self):
        repo = FakeMetricsRepo(_samples(evaluated_count=0, correct_count=0))
        result = await metrics_dashboard(_admin(), F63Request(query=WINDOW), repo=repo)
        self.assertIsNone(labelled_accuracy(result.metrics))

    async def test_demo_excluded_by_default(self):
        repo = FakeMetricsRepo(_samples(enquiry_count=10), demo=_samples(enquiry_count=99))
        result = await metrics_dashboard(_admin(), F63Request(query=WINDOW), repo=repo)
        self.assertFalse(repo.last_query.include_demo)   # default excludes demo
        self.assertEqual(result.metrics.enquiry_count, 10)  # demo traffic not blended in

    async def test_demo_included_only_when_requested(self):
        repo = FakeMetricsRepo(_samples(enquiry_count=10), demo=_samples(enquiry_count=99))
        window = MetricsQuery(start=WINDOW.start, end=WINDOW.end, include_demo=True)
        result = await metrics_dashboard(_admin(), F63Request(query=window), repo=repo)
        self.assertEqual(result.metrics.enquiry_count, 99)

    async def test_non_staff_forbidden(self):
        repo = FakeMetricsRepo(_samples())
        customer = ActorContext(user_id=uuid4(), request_id=uuid4(), roles=[])
        with self.assertRaises(PartsIQError) as ctx:
            await metrics_dashboard(customer, F63Request(query=WINDOW), repo=repo)
        self.assertEqual(ctx.exception.http_status, 403)

    async def test_dependency_failure_propagates(self):
        repo = FakeMetricsRepo(None, raises=PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="down"))
        with self.assertRaises(PartsIQError) as ctx:
            await metrics_dashboard(_admin(), F63Request(query=WINDOW), repo=repo)
        self.assertEqual(ctx.exception.code, "DEPENDENCY_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
