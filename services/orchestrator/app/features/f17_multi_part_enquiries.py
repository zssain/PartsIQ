"""F17 Multi-part enquiries (owner: orchestrator; depends on 09-14, 19, 20).

An enquiry may carry up to 20 items, each with its own quantity, machine/configuration,
candidate set and selection, and its own resolution status. The hard invariant this module
owns: stock is planned ONCE across the combined requested quantities per selected part, then
distributed to items in ordinal order — so two line items that request the same part cannot
each consume the same available stock (no double counting). A non-positive quantity is
rejected, and any item that is not ``ready`` is returned in ``unresolved_item_ids`` so a single
unresolved item blocks a final all-items approval.

resolve_items is pure over an injected ItemPlanningStore; the live Postgres adapter
(enquiry_items + fulfilment_plans, RLS-scoped) is wired by the orchestrator owner and is
BLOCKED here. The deterministic allocation mirrors the aggregate (part, warehouse) recompute
the verification gate performs (app.verification.check_allocation).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from partsiq_common.contracts import ActorContext, Contract, ItemInput, ItemState
from partsiq_common.errors import PartsIQError

MAX_ITEMS = 20


class F17Request(Contract):
    enquiry_id: UUID
    expected_revision: int


class F17Result(Contract):
    items: list[ItemState]
    unresolved_item_ids: list[UUID]


@dataclass(frozen=True, slots=True)
class ItemPlanRow:
    """One enquiry line as the store yields it (quantity may be absent or, erroneously, <= 0)."""

    id: UUID
    description: str
    quantity: Decimal | None
    configuration_id: int | None
    candidate_part_ids: tuple[int, ...]
    selected_part_id: int | None
    source_message_id: UUID
    source_start: int
    source_end: int


@dataclass(frozen=True, slots=True)
class ItemPlan:
    authorized: bool
    is_demo: bool
    session_id: UUID | None
    session_generation: int | None
    current_revision: int
    rows: tuple[ItemPlanRow, ...]
    available: dict[int, Decimal] = field(default_factory=dict)  # selected part_id -> available units


class ItemPlanningStore(Protocol):
    """Loads an enquiry's line items + per-part available stock (RLS-scoped in production)."""

    async def load_plan(self, actor: ActorContext, enquiry_id: UUID) -> ItemPlan: ...


def _provisional_status(row: ItemPlanRow) -> str:
    """Status before stock distribution: can this line even be allocated?"""
    if not row.candidate_part_ids:
        return "unresolved"
    if row.selected_part_id is None or row.configuration_id is None or row.quantity is None:
        return "needs_information"
    return "ready"


def unresolved_ids(items: list[ItemState]) -> list[UUID]:
    """The single readiness rule (shared with handlers.unresolved_items): not-ready blocks approval."""
    return [item.id for item in items if item.status != "ready"]


def can_approve_all(items: list[ItemState]) -> bool:
    """One unresolved item blocks a final all-items approval (F17)."""
    return not unresolved_ids(items)


def _plan(rows: tuple[ItemPlanRow, ...], available: dict[int, Decimal]) -> list[ItemState]:
    provisional = {row.id: _provisional_status(row) for row in rows}
    pool = dict(available)
    states: list[ItemState] = []
    for row in rows:  # input order == ordinal line order: earlier lines win contested stock
        status = provisional[row.id]
        if status == "ready":
            have = pool.get(row.selected_part_id, Decimal("0"))  # type: ignore[arg-type]
            give = min(have, row.quantity)  # type: ignore[type-var]
            pool[row.selected_part_id] = have - give  # type: ignore[index]
            # A repeated part draws from the SAME shared pool, so a later line can only take
            # what earlier lines left — it cannot re-count the same available stock.
            status = "ready" if give >= row.quantity else "unavailable"  # type: ignore[operator]
        states.append(
            ItemState(
                id=row.id,
                request=ItemInput(
                    description=row.description,
                    quantity=row.quantity,
                    source_message_id=row.source_message_id,
                    source_start=row.source_start,
                    source_end=row.source_end,
                ),
                configuration_id=row.configuration_id,
                candidate_part_ids=list(row.candidate_part_ids),
                selected_part_id=row.selected_part_id,
                status=status,  # type: ignore[arg-type]
            )
        )
    return states


def _authorize(actor: ActorContext, plan: ItemPlan) -> None:
    """Deny as NOT_FOUND (never leak existence). Demo review requires the own active session."""
    if not plan.authorized:
        raise PartsIQError("NOT_FOUND", internal_detail="enquiry not visible to this actor")
    if plan.is_demo and (
        actor.session_id != plan.session_id or actor.session_generation != plan.session_generation
    ):
        raise PartsIQError("NOT_FOUND", internal_detail="demo resolution requires the own active session")


async def resolve_items(actor: ActorContext, request: F17Request, *, store: ItemPlanningStore) -> F17Result:
    """Resolve every item independently, plan stock once per part, return states + unresolved ids."""
    plan = await store.load_plan(actor, request.enquiry_id)
    _authorize(actor, plan)
    if request.expected_revision != plan.current_revision:
        raise PartsIQError("STALE_REVISION", internal_detail="a newer revision exists; re-resolve the current items")
    if len(plan.rows) > MAX_ITEMS:
        raise PartsIQError("MALFORMED_REQUEST", internal_detail=f"an enquiry may carry at most {MAX_ITEMS} items")
    for row in plan.rows:
        if row.quantity is not None and row.quantity <= 0:
            raise PartsIQError("VALIDATION_FAILED", internal_detail="item quantity must be positive")
    states = _plan(plan.rows, plan.available)
    return F17Result(items=states, unresolved_item_ids=unresolved_ids(states))
