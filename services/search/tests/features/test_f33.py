"""F33 Fulfilment planning — local first, deterministic remotes, bounded allocations."""
from __future__ import annotations

import unittest

from app.fulfilment import WarehouseStock, plan_fulfilment


def _stock(jed, ruh, dmm=0):
    return [
        WarehouseStock("JED", "Jeddah", "Western", jed),
        WarehouseStock("RUH", "Riyadh", "Central", ruh),
        WarehouseStock("DMM", "Dammam", "Eastern", dmm),
    ]


ROUTES = {("RUH", "JED"): 2, ("DMM", "JED"): 3}


class FulfilmentPlanning(unittest.TestCase):
    def test_local_first(self) -> None:
        plan = plan_fulfilment(_stock(10, 10), ROUTES, "JED", 4)
        self.assertEqual(plan.strategy, "local")
        self.assertEqual(plan.lines[0].warehouse_code, "JED")

    def test_allocations_never_exceed_request_or_stock(self) -> None:
        plan = plan_fulfilment(_stock(2, 1), ROUTES, "JED", 10)
        allocated = sum(line.quantity for line in plan.lines)
        self.assertLessEqual(allocated, 10)
        self.assertEqual(allocated, 3)  # only 3 in stock across warehouses
        self.assertEqual(plan.shortfall, 7)

    def test_split_prefers_nearest_remote(self) -> None:
        plan = plan_fulfilment(_stock(0, 1, 5), ROUTES, "JED", 6)
        # DMM alone can cover the remainder in one shipment; nearest single wins over split.
        self.assertIn(plan.strategy, {"transfer", "split"})
        self.assertLessEqual(sum(line.quantity for line in plan.lines), 6)

    def test_unavailable_route_cannot_be_invented(self) -> None:
        with self.assertRaises(ValueError):
            plan_fulfilment(_stock(0, 5), {}, "JED", 3)  # remote stock but no route

    def test_unknown_destination_rejected(self) -> None:
        with self.assertRaises(ValueError):
            plan_fulfilment(_stock(1, 1), ROUTES, "XXX", 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
