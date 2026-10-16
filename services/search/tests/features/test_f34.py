"""F34 Transfer estimates — integer transfer_days from the approved route; local == 0."""
from __future__ import annotations

import unittest

from app.fulfilment import WarehouseStock, plan_fulfilment


def _stock(jed, ruh):
    return [WarehouseStock("JED", "Jeddah", "Western", jed), WarehouseStock("RUH", "Riyadh", "Central", ruh)]


class TransferEstimates(unittest.TestCase):
    def test_local_availability_is_zero_transfer_days(self) -> None:
        plan = plan_fulfilment(_stock(10, 0), {("RUH", "JED"): 2}, "JED", 3)
        self.assertEqual(plan.estimated_transfer_days, 0)

    def test_transfer_days_carried_from_route(self) -> None:
        plan = plan_fulfilment(_stock(0, 10), {("RUH", "JED"): 2}, "JED", 3)
        self.assertEqual(plan.estimated_transfer_days, 2)
        self.assertIsInstance(plan.lines[0].transfer_days, int)

    def test_no_route_yields_unavailable_not_invented_promise(self) -> None:
        with self.assertRaises(ValueError):
            plan_fulfilment(_stock(0, 10), {}, "JED", 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
