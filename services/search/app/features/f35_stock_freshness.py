"""F35 Stock freshness (owner: search; depends on 06, 12, 14, 20).

Compares each planned allocation's ``stock_updated_at`` against a configurable freshness window
and re-reads CURRENT stock, so review and approval never rest on a stale snapshot. An item is
flagged (``changed_item_ids``) when its stock timestamp is in the future (a clock anomaly), is
older than ``max_age_seconds``, when the current snapshot has refreshed since planning, or when
the current available can no longer cover the allocated quantity. ``fresh`` is True only when no
item is flagged — a stale snapshot is surfaced as not-fresh and never becomes a delivery
guarantee. During approval a non-fresh result drives a 409 and re-planning.

Pure over an injected StockReader; the live pgvector/stock adapter is BLOCKED here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from partsiq_common.contracts import ActorContext, Contract, VerifiedFacts
from partsiq_common.errors import PartsIQError


class F35Request(Contract):
    facts: VerifiedFacts
    max_age_seconds: int


class F35Result(Contract):
    fresh: bool
    changed_item_ids: list[UUID]
    checked_at: datetime


@dataclass(frozen=True, slots=True)
class CurrentStock:
    available: Decimal
    updated_at: datetime


class StockReader(Protocol):
    async def current_stock(self, part_id: int, warehouse_id: int) -> CurrentStock | None:
        """Current netted available + its timestamp for a (part, warehouse), or None if unknown now."""
        ...


async def check_stock_freshness(
    actor: ActorContext, request: F35Request, *, reader: StockReader, now: datetime
) -> F35Result:
    """Flag any item whose planned stock is stale, future-dated, refreshed, or no longer sufficient."""
    if request.max_age_seconds <= 0:
        raise PartsIQError("VALIDATION_FAILED", internal_detail="max_age_seconds must be positive")
    changed: set[UUID] = set()
    for item in request.facts.items:
        for allocation in item.allocations:
            stamped = allocation.stock_updated_at
            if stamped > now:  # future timestamp — a clock anomaly, never trusted as fresh
                changed.add(item.item_id)
                continue
            if (now - stamped).total_seconds() > request.max_age_seconds:  # older than the window
                changed.add(item.item_id)
                continue
            current = await reader.current_stock(item.part_id, allocation.warehouse_id)
            if current is None or current.available < allocation.quantity:  # allocation no longer possible
                changed.add(item.item_id)
                continue
            if current.updated_at != stamped:  # stock refreshed since planning -> re-plan
                changed.add(item.item_id)
    return F35Result(fresh=not changed, changed_item_ids=sorted(changed, key=str), checked_at=now)
