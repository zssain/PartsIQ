"""Fulfilment planning for the selected parts of an enquiry (prompt 11 — F17/F32/F33/F34/F35).

Given the ``ready`` items of an :class:`~partsiq.core.contracts.EnquiryState` (each with a
selected compatible part and a confirmed quantity), this module plans warehouse allocations
and produces the :class:`~partsiq.core.contracts.VerifiedItem`s that the deterministic
verification gate (prompt 12) later re-checks. It consolidates demand per selected part across
every item, fills the destination warehouse first and then the nearest reachable warehouses by
integer transfer lead time, distributes the allocations back to the items in ordinal order, and
keeps any shortage explicit.

It is a planning RECOMMENDATION only (F33): it NEVER reserves stock and NEVER creates an order.
Each :class:`~partsiq.core.contracts.Allocation` carries the stock observation timestamp
(``stock_updated_at``) so a reviewer sees the exact snapshot the plan used, and integer
``transfer_days`` are carried verbatim from the stored route — a missing route is surfaced as
unavailable, never an invented one-day promise (F34). Stock freshness is enforced against a
configured limit: a reading older than ``max_age_seconds`` (or one stamped in the future) is
unusable, so the item is short rather than planned against stale data (F35) — stale stock never
becomes a delivery guarantee.

The allocation algorithm is the legacy ``services/search/app/fulfilment.py`` (foundation 06)
local-first ordering, adapted to integer warehouse ids and ``Decimal`` quantities so the plan
is symmetric with the verification gate's aggregate (part, warehouse) recompute
(``enquiries.verification.check_allocation``) and with the multi-item demand consolidation of the
legacy F17 module (``services/orchestrator/app/features/f17_multi_part_enquiries.py``). No LLM
participates anywhere here.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from partsiq.core.api_models import PlanView
from partsiq.core.contracts import Allocation, EnquiryState, VerifiedItem
from partsiq.core.errors import PartsIQError

# ---------------------------------------------------------------------------
# Deterministic inputs. A stock reading is already netted (on-hand minus reserved),
# keyed by integer warehouse id; a negative net is clamped to zero so it never counts
# as stock (F32). Transfer routes carry integer lead times (F34).
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StockReading:
    """A netted stock reading for one (part, warehouse) at one observation time."""

    part_id: int
    warehouse_id: int
    available: Decimal
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class PartDescriptor:
    """The catalogue facts a plan line needs for a selected part (code-owned, not model text)."""

    part_id: int
    part_number: str
    name_en: str
    name_ar: str
    source_reference: str
    evidence_id: UUID


@dataclass(frozen=True, slots=True)
class FulfilmentInputs:
    """Everything the planner needs, injected so the planner is pure and testable offline.

    ``now`` and ``max_age_seconds`` drive the freshness check (F35). ``destination_warehouse_id``
    is the enquiry's delivery warehouse (local-first). ``stock`` is every netted reading for the
    selected parts; ``transfer_days`` maps ``(source_warehouse_id, destination_warehouse_id)`` to
    the stored integer lead time; ``parts`` carries the catalogue facts per selected part.
    """

    destination_warehouse_id: int
    stock: list[StockReading]
    transfer_days: dict[tuple[int, int], int]
    parts: dict[int, PartDescriptor]
    now: datetime
    max_age_seconds: int


class FulfilmentSource(Protocol):
    """Loads the inputs above for an enquiry revision (RLS-scoped in production).

    The live PostgreSQL adapter (stock_levels + warehouse_transfer_routes, reading the active
    catalogue snapshot) is BLOCKED in this environment and wired by the owner; tests inject a
    deterministic fake seeded from the seed-42 fixture catalogue.
    """

    async def load(self, state: EnquiryState) -> FulfilmentInputs: ...


# ---------------------------------------------------------------------------
# Freshness (F35): a reading is usable only when it is neither in the future nor
# older than the configured limit. Unknown/expired stock stays unknown — it is
# never treated as available.
# ---------------------------------------------------------------------------
def is_fresh(observed_at: datetime, now: datetime, max_age_seconds: int) -> bool:
    """True when ``observed_at`` is within ``[now - max_age, now]`` (F35).

    A future timestamp is rejected (clock skew / bad data), and a reading older than the limit
    is stale. Either way the reading cannot back an allocation.
    """
    if observed_at > now:
        return False
    return now - observed_at <= timedelta(seconds=max_age_seconds)


@dataclass(frozen=True, slots=True)
class _Fill:
    """One consolidated fill of demand for a part from one warehouse."""

    warehouse_id: int
    quantity: Decimal
    transfer_days: int
    observed_at: datetime


def _plan_part(
    part_id: int,
    demand: Decimal,
    inputs: FulfilmentInputs,
) -> tuple[list[_Fill], Decimal]:
    """Plan the CONSOLIDATED demand for one part. Returns (fills, shortage).

    Local first (zero transfer days), then the nearest reachable warehouses by integer transfer
    lead time. Only fresh readings are usable (F35). A remote warehouse with no stored route to
    the destination cannot contribute — its stock is simply not reachable (F34), never invented.
    """
    usable = {
        reading.warehouse_id: reading
        for reading in inputs.stock
        if reading.part_id == part_id
        and is_fresh(reading.observed_at, inputs.now, inputs.max_age_seconds)
    }
    dest = inputs.destination_warehouse_id

    def available(reading: StockReading) -> Decimal:
        return reading.available if reading.available > 0 else Decimal("0")

    remaining = demand
    fills: list[_Fill] = []

    local = usable.get(dest)
    if local is not None and available(local) > 0:
        take = min(available(local), remaining)
        if take > 0:
            fills.append(_Fill(dest, take, 0, local.observed_at))
            remaining -= take

    if remaining > 0:
        # Reachable remotes: stock > 0 AND a stored route to the destination exists.
        remotes = [
            reading
            for wid, reading in usable.items()
            if wid != dest
            and available(reading) > 0
            and (wid, dest) in inputs.transfer_days
        ]
        remotes.sort(key=lambda r: (inputs.transfer_days[(r.warehouse_id, dest)], r.warehouse_id))
        # A single remote that covers the whole remainder avoids a split shipment.
        single = sorted(
            (r for r in remotes if available(r) >= remaining),
            key=lambda r: (inputs.transfer_days[(r.warehouse_id, dest)], r.warehouse_id),
        )
        ordered = single[:1] if single else remotes
        for reading in ordered:
            if remaining <= 0:
                break
            take = min(available(reading), remaining)
            if take <= 0:
                continue
            fills.append(
                _Fill(
                    reading.warehouse_id,
                    take,
                    inputs.transfer_days[(reading.warehouse_id, dest)],
                    reading.observed_at,
                )
            )
            remaining -= take

    shortage = remaining if remaining > 0 else Decimal("0")
    return fills, shortage


def _distribute(
    fills: list[_Fill],
    item_demands: list[tuple[UUID, Decimal]],
) -> dict[UUID, list[_Fill]]:
    """Distribute a part's consolidated fills back to its items in ordinal order (F17).

    Earlier line items win contested stock: a later line can only draw what earlier lines left
    from the SAME consolidated pool, so two lines requesting one part never double-count stock.
    """
    # A mutable per-warehouse pool preserving the local-first fill order.
    pool: list[list] = [[f.warehouse_id, f.quantity, f.transfer_days, f.observed_at] for f in fills]
    out: dict[UUID, list[_Fill]] = {item_id: [] for item_id, _ in item_demands}
    for item_id, demand in item_demands:
        need = demand
        for entry in pool:
            if need <= 0:
                break
            if entry[1] <= 0:
                continue
            take = min(entry[1], need)
            out[item_id].append(_Fill(entry[0], take, entry[2], entry[3]))
            entry[1] -= take
            need -= take
    return out


def plan_items(state: EnquiryState, inputs: FulfilmentInputs) -> list[VerifiedItem]:
    """Plan fulfilment for every ``ready`` item and return the typed :class:`VerifiedItem`s.

    Pure over ``(state, inputs)``: no I/O, no provider call, no reservation. Demand is
    consolidated per selected part across items, planned once (local-first), then distributed
    back to items in ordinal order. Each item's shortage is explicit (requested minus allocated).
    """
    ready = [
        item
        for item in state.items
        if item.status == "ready"
        and item.selected_part_id is not None
        and item.configuration_id is not None
        and item.request.quantity is not None
    ]

    # 1. Consolidate demand per selected part, preserving item ordinal order.
    demand_by_part: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    items_by_part: dict[int, list[tuple[UUID, Decimal]]] = defaultdict(list)
    for item in ready:
        part_id = item.selected_part_id
        quantity = item.request.quantity
        assert part_id is not None and quantity is not None  # narrowed by the filter above
        demand_by_part[part_id] += quantity
        items_by_part[part_id].append((item.id, quantity))

    # 2. Plan each part once, then distribute its fills back to its items.
    fills_by_item: dict[UUID, list[_Fill]] = {}
    for part_id, demand in demand_by_part.items():
        if part_id not in inputs.parts:
            raise PartsIQError(
                "STALE_CATALOGUE",
                detail="A selected part is no longer in the active catalogue.",
                internal_detail=f"selected part {part_id} missing from plan inputs",
            )
        fills, _shortage = _plan_part(part_id, demand, inputs)
        fills_by_item.update(_distribute(fills, items_by_part[part_id]))

    # 3. Build the typed VerifiedItem for each ready item in its original order.
    verified: list[VerifiedItem] = []
    for item in ready:
        part_id = item.selected_part_id
        quantity = item.request.quantity
        configuration_id = item.configuration_id
        assert part_id is not None and quantity is not None and configuration_id is not None
        descriptor = inputs.parts[part_id]
        fills = fills_by_item.get(item.id, [])
        allocations = [
            Allocation(
                warehouse_id=fill.warehouse_id,
                quantity=fill.quantity,
                transfer_days=fill.transfer_days,
                stock_updated_at=fill.observed_at,
            )
            for fill in fills
            if fill.quantity > 0
        ]
        allocated = sum((fill.quantity for fill in fills), Decimal("0"))
        shortage = quantity - allocated
        if shortage < 0:
            shortage = Decimal("0")
        verified.append(
            VerifiedItem(
                item_id=item.id,
                configuration_id=configuration_id,
                part_id=part_id,
                part_number=descriptor.part_number,
                name_en=descriptor.name_en,
                name_ar=descriptor.name_ar,
                requested_quantity=quantity,
                allocations=allocations,
                shortage=shortage,
                source_reference=descriptor.source_reference,
                evidence_id=descriptor.evidence_id,
            )
        )
    return verified


async def plan_enquiry(
    state: EnquiryState,
    *,
    source: FulfilmentSource,
    stock_snapshot_id: UUID | None = None,
) -> PlanView:
    """Application entry point for the PLAN step: load inputs, plan, return a typed PlanView.

    Loads the stock/route inputs for the current enquiry revision, plans the ready items and
    returns a :class:`PlanView`. The result is a typed value handed straight to the workflow, not
    a specialist-agent message (IMPLEMENTATION STEP 10). No reservation and no order are created.
    """
    inputs = await source.load(state)
    items = plan_items(state, inputs)
    return PlanView(
        enquiry_id=state.enquiry_id,
        revision=state.revision,
        items=items,
        stock_snapshot_id=stock_snapshot_id,
    )
