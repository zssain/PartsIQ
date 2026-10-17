"""Fulfilment planning across regional warehouses.

Ported verbatim (behaviour unchanged) from the legacy ``services/search/app/fulfilment.py``
(foundation 06). This is a planning RECOMMENDATION only; it never reserves stock and never
creates an order (F33). ``available`` is the already-netted value (on-hand minus reserved) read
from a single stock snapshot; a negative net is clamped to zero so it never counts as stock
(F32). Transfer lead times are integer ``transfer_days`` carried from the approved route; a
missing route is surfaced as unavailable rather than invented (F34).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

Strategy = Literal["local", "transfer", "split", "backorder"]


@dataclass(frozen=True, slots=True)
class WarehouseStock:
    warehouse_code: str
    warehouse_name: str
    region: str
    available: int


@dataclass(frozen=True, slots=True)
class FulfilmentLine:
    warehouse_code: str
    quantity: int
    transfer_days: int


@dataclass(frozen=True, slots=True)
class FulfilmentPlan:
    strategy: Strategy
    lines: tuple[FulfilmentLine, ...]
    estimated_transfer_days: int | None
    shortfall: int
    message: str


def plan_fulfilment(
    stock: Sequence[WarehouseStock],
    transfer_days: Mapping[tuple[str, str], int],
    destination: str,
    quantity: int,
) -> FulfilmentPlan:
    """Fill from the destination first, then from the nearest warehouses by transfer lead time.

    This is a planning recommendation only; it does not reserve stock.
    """
    if quantity < 1:
        raise ValueError("quantity must be at least 1")
    by_code = {entry.warehouse_code: entry for entry in stock}
    if destination not in by_code:
        raise ValueError(f"Unknown destination warehouse {destination}")

    remaining = quantity
    lines: list[FulfilmentLine] = []

    local_available = max(by_code[destination].available, 0)
    if local_available:
        take = min(local_available, remaining)
        lines.append(FulfilmentLine(destination, take, 0))
        remaining -= take

    if remaining:
        remotes = [entry for entry in stock if entry.warehouse_code != destination and entry.available > 0]
        for entry in remotes:
            if (entry.warehouse_code, destination) not in transfer_days:
                raise ValueError(f"No transfer route from {entry.warehouse_code} to {destination}")
        # A single remote warehouse that can cover the remainder avoids a split shipment.
        single = sorted(
            (e for e in remotes if e.available >= remaining),
            key=lambda e: transfer_days[(e.warehouse_code, destination)],
        )
        ordered = single[:1] if single else sorted(remotes, key=lambda e: transfer_days[(e.warehouse_code, destination)])
        for entry in ordered:
            if not remaining:
                break
            take = min(entry.available, remaining)
            lines.append(FulfilmentLine(entry.warehouse_code, take, transfer_days[(entry.warehouse_code, destination)]))
            remaining -= take

    estimated = max((line.transfer_days for line in lines), default=None)
    if remaining:
        supplied = quantity - remaining
        return FulfilmentPlan(
            "backorder", tuple(lines), estimated, remaining,
            f"Only {supplied} of {quantity} available across all warehouses; {remaining} must be back-ordered.",
        )
    if len(lines) == 1 and lines[0].warehouse_code == destination:
        return FulfilmentPlan("local", tuple(lines), 0, 0, f"All {quantity} available at {destination}.")
    if len(lines) == 1:
        line = lines[0]
        return FulfilmentPlan(
            "transfer", tuple(lines), estimated, 0,
            f"Not available at {destination}; transfer {quantity} from {line.warehouse_code} "
            f"(approximately {line.transfer_days} day(s)).",
        )
    return FulfilmentPlan(
        "split", tuple(lines), estimated, 0,
        f"Fulfil from {len(lines)} warehouses; complete in approximately {estimated} day(s).",
    )
