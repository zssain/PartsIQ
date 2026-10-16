"""F32 Warehouse stock — the planner uses net available (on_hand − reserved) and clamps it.

plan_fulfilment is the single snapshot both the display and the planner read from. A
warehouse's available is the already-netted value; a negative value is blocked (clamped to
zero, never shown as stock), an unknown destination is rejected, and an insufficient total
back-orders the remainder rather than inventing stock.
"""
from __future__ import annotations

import unittest

from app.fulfilment import WarehouseStock, plan_fulfilment

ROUTES = {("RUH", "JED"): 2, ("DMM", "JED"): 3}


def _stock(jed, ruh=0, dmm=0):
    return [
        WarehouseStock("JED", "Jeddah", "Western", jed),
        WarehouseStock("RUH", "Riyadh", "Central", ruh),
        WarehouseStock("DMM", "Dammam", "Eastern", dmm),
    ]


class WarehouseStockPlanning(unittest.TestCase):
    def test_local_net_available_fills_locally(self):  # success
        plan = plan_fulfilment(_stock(jed=5), ROUTES, "JED", 3)
        self.assertEqual(plan.strategy, "local")
        self.assertEqual(plan.shortfall, 0)

    def test_negative_local_stock_is_blocked(self):
        # A negative net at the destination must not count as stock; it is clamped to zero,
        # so the order transfers from a remote warehouse instead.
        plan = plan_fulfilment(_stock(jed=-4, ruh=10), ROUTES, "JED", 3)
        self.assertEqual(plan.strategy, "transfer")
        self.assertTrue(all(line.warehouse_code != "JED" for line in plan.lines))

    def test_unknown_destination_rejected(self):  # invalid-input
        with self.assertRaises(ValueError):
            plan_fulfilment(_stock(jed=5), ROUTES, "XXX", 1)

    def test_insufficient_total_backorders_remainder(self):
        plan = plan_fulfilment(_stock(jed=1, ruh=1), ROUTES, "JED", 10)
        self.assertEqual(plan.strategy, "backorder")
        self.assertEqual(plan.shortfall, 8)

    def test_quantity_must_be_positive(self):
        with self.assertRaises(ValueError):
            plan_fulfilment(_stock(jed=5), ROUTES, "JED", 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
