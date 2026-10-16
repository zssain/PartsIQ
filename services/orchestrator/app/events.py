"""Durable event consumption.

Contract: ``async def consume_event(event_id: UUID) -> EventOutcome``.

Events live in a DB inbox. A consumer claims an event under a lease and locks the
enquiry; after claiming, it rechecks that the event's revision and session generation
still match the enquiry. A duplicate (already-claimed) event is obsolete, so publication
never repeats; a stale-revision/old-generation event is consumed as obsolete and audited;
a handler error becomes a retry (F50). The event store is injected for offline testing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from partsiq_common.contracts import EventOutcome


@dataclass(frozen=True, slots=True)
class ClaimedEvent:
    event_id: UUID
    enquiry_id: UUID
    revision: int
    session_generation: int | None


class EventStore(Protocol):
    async def claim(self, event_id: UUID) -> ClaimedEvent | None: ...

    async def current(self, enquiry_id: UUID) -> tuple[int, int | None] | None: ...

    async def mark_obsolete(self, event_id: UUID) -> None: ...

    async def mark_processed(self, event_id: UUID) -> None: ...

    async def mark_retry(self, event_id: UUID) -> None: ...

    async def run(self, claim: ClaimedEvent) -> None: ...


async def consume_event(event_id: UUID, *, store: EventStore) -> EventOutcome:
    claim = await store.claim(event_id)
    if claim is None:
        # Already claimed/processed: duplicate delivery must not repeat work (F50).
        return EventOutcome(event_id=event_id, state="obsolete")

    current = await store.current(claim.enquiry_id)
    if current is None:
        return EventOutcome(event_id=event_id, state="failed")
    current_revision, current_generation = current

    stale_revision = claim.revision != current_revision
    stale_generation = claim.session_generation is not None and claim.session_generation != current_generation
    if stale_revision or stale_generation:
        await store.mark_obsolete(event_id)
        return EventOutcome(event_id=event_id, state="obsolete")

    try:
        await store.run(claim)
    except Exception:  # noqa: BLE001 - any handler failure is a retryable outcome, not a crash
        await store.mark_retry(event_id)
        return EventOutcome(event_id=event_id, state="retry")

    await store.mark_processed(event_id)
    return EventOutcome(event_id=event_id, state="processed")
