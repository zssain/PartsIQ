"""F33 Fulfilment planning facade (helper ``fulfilment.plan_enquiry``).

Returns the fulfilment PLAN for a whole enquiry: for every ready item, the warehouse allocations
(local-first, then nearest by integer transfer lead time) and any explicit shortage, plus the
stock snapshot id the plan rested on. This is a planning RECOMMENDATION only — it NEVER reserves
stock and NEVER creates an order (F33); a negative net is clamped (F32) and a missing route is
surfaced as unavailable, never an invented promise (F34). Review access; a foreign enquiry is
NOT_FOUND.

Read through the shared :class:`ItemStateSource`; the DB-backed stock/route store is not configured
in this environment, so a clean 503 is surfaced rather than a fabricated plan. Thin, injectable
adapter.
"""
from __future__ import annotations

from uuid import UUID

from partsiq.core.api_models import PlanView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.features.f20_machine_identification import ItemStateSource, require_item_state


async def plan_enquiry(
    actor: ActorContext,
    enquiry_id: UUID,
    *,
    container: AppContainer,
    source: ItemStateSource | None = None,
) -> PlanView:
    """Return the fulfilment plan (allocations + shortage) for the whole enquiry (review)."""
    source = source or require_item_state(container)
    return await source.read_plan(actor, enquiry_id)
