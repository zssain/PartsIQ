"""F35 Stock freshness facade (helper ``fulfilment.check_freshness``).

Reports whether the enquiry's planned stock snapshot is still FRESH: ``fresh`` is True only when
the planning snapshot is neither in the future (a clock anomaly) nor older than ``max_age_seconds``
and still covers the planned allocations; otherwise ``fresh`` is False with a ``reason_code`` so a
stale snapshot never becomes a silent delivery guarantee (F35) and drives a 409 + re-plan during
approval. Review access; a foreign enquiry is NOT_FOUND.

Read through the shared :class:`ItemStateSource`; the DB-backed stock snapshot is not configured in
this environment, so a clean 503 is surfaced rather than a fabricated freshness verdict. Thin,
injectable adapter.
"""
from __future__ import annotations

from uuid import UUID

from partsiq.core.api_models import FreshnessView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.features.f20_machine_identification import ItemStateSource, require_item_state


async def check_freshness(
    actor: ActorContext,
    enquiry_id: UUID,
    *,
    container: AppContainer,
    source: ItemStateSource | None = None,
) -> FreshnessView:
    """Report whether the enquiry's planned stock snapshot is still fresh (review access)."""
    source = source or require_item_state(container)
    return await source.read_freshness(actor, enquiry_id)
