"""Event-consumer loop.

Serializes processing per enquiry by consuming DB inbox events one at a time under a
lease. Pure orchestration over the injected event store; the store holds the lock and
runs the graph. Kept thin so consume_event stays the single decision point (F50).
"""
from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from app.events import EventStore, consume_event
from partsiq_common.contracts import EventOutcome


async def process_batch(event_ids: Sequence[UUID], *, store: EventStore) -> list[EventOutcome]:
    """Consume a batch of events in order; each resolves independently (no exceptions escape)."""
    outcomes: list[EventOutcome] = []
    for event_id in event_ids:
        outcomes.append(await consume_event(event_id, store=store))
    return outcomes
