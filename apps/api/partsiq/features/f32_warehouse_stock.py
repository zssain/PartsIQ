"""F32 Warehouse stock facade (helper ``fulfilment.stock_for_selection``).

Returns the per-warehouse netted stock for an item's SELECTED part: each row is the already-netted
available (on-hand minus reserved) read from one stock snapshot, with a warehouse that has no
reading reporting zero and a negative net clamped to zero so it never counts as stock (F32). The
view carries the snapshot id and a ``stale`` flag; a reading is NEVER a reservation (F33). Review
access; a foreign enquiry/item is NOT_FOUND.

Read through the shared :class:`ItemStateSource`; the DB-backed stock snapshot is not configured in
this environment, so a clean 503 is surfaced rather than a fabricated reading. Thin, injectable
adapter.
"""
from __future__ import annotations

from uuid import UUID

from partsiq.core.api_models import StockView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.features.f20_machine_identification import ItemStateSource, require_item_state


async def stock_for_selection(
    actor: ActorContext,
    enquiry_id: UUID,
    item_id: UUID,
    *,
    container: AppContainer,
    source: ItemStateSource | None = None,
) -> StockView:
    """Return per-warehouse netted stock for one item's selected part (review access)."""
    source = source or require_item_state(container)
    return await source.read_stock(actor, enquiry_id, item_id)
