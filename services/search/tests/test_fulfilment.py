import pytest

from app.fulfilment import WarehouseStock, plan_fulfilment

ROUTES = {
    ("JED", "RUH"): 2, ("RUH", "JED"): 2,
    ("RUH", "DMM"): 1, ("DMM", "RUH"): 1,
    ("JED", "DMM"): 3, ("DMM", "JED"): 3,
}


def _stock(jed: int, ruh: int, dmm: int) -> list[WarehouseStock]:
    return [
        WarehouseStock("JED", "Western", "Western", jed),
        WarehouseStock("RUH", "Central", "Central", ruh),
        WarehouseStock("DMM", "Eastern", "Eastern", dmm),
    ]


def test_local_stock_is_preferred() -> None:
    plan = plan_fulfilment(_stock(1, 10, 10), ROUTES, "RUH", 4)
    assert plan.strategy == "local" and plan.estimated_transfer_days == 0


def test_nearest_single_warehouse_is_chosen_for_transfer() -> None:
    plan = plan_fulfilment(_stock(10, 0, 10), ROUTES, "RUH", 4)
    assert plan.strategy == "transfer"
    assert plan.lines[0].warehouse_code == "DMM" and plan.estimated_transfer_days == 1


def test_local_partial_plus_transfer_is_split() -> None:
    plan = plan_fulfilment(_stock(2, 0, 10), ROUTES, "JED", 5)
    assert plan.strategy == "split"
    assert [(l.warehouse_code, l.quantity) for l in plan.lines] == [("JED", 2), ("DMM", 3)]


def test_insufficient_total_stock_is_backordered() -> None:
    plan = plan_fulfilment(_stock(1, 1, 1), ROUTES, "JED", 5)
    assert plan.strategy == "backorder" and plan.shortfall == 2


def test_invalid_inputs_are_rejected() -> None:
    with pytest.raises(ValueError):
        plan_fulfilment(_stock(1, 1, 1), ROUTES, "XXX", 1)
    with pytest.raises(ValueError):
        plan_fulfilment(_stock(1, 1, 1), ROUTES, "JED", 0)
