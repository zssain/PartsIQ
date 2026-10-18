"""F21 Machine mismatch detection facade (helper ``search.check_hints``).

Returns whether an item's model and serial HINTS conflict (e.g. a serial that belongs to a
different model than the quoted model code), with a bilingual clarifying question when they do.
Detection is the deterministic identification algorithm (:mod:`partsiq.search.identification`):
conflicting hints never silently override each other and no LLM decides the mismatch (F21). Owner
access; a foreign enquiry/item is NOT_FOUND.

The per-item hint state is read through the shared :class:`ItemStateSource`; that DB-backed store
is not configured in this environment, so the read surfaces a clean 503 rather than inventing a
mismatch verdict. The facade is a thin, injectable adapter (unit-testable with a fake).
"""
from __future__ import annotations

from uuid import UUID

from partsiq.core.api_models import MismatchView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.features.f20_machine_identification import ItemStateSource, require_item_state


async def check_hints(
    actor: ActorContext,
    enquiry_id: UUID,
    item_id: UUID,
    *,
    container: AppContainer,
    source: ItemStateSource | None = None,
) -> MismatchView:
    """Return the model/serial mismatch verdict for one enquiry item (owner access)."""
    source = source or require_item_state(container)
    return await source.read_mismatch(actor, enquiry_id, item_id)
