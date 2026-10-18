"""F27 Match explanations facade (helper ``search.explain_selection``).

Returns the human-readable reasons the selected candidate was offered for an item (e.g. quoted
part number, lexical match, semantic match, superseded number resolved), plus the catalogue
``source_reference`` that backs the fitment and the catalogue version. The reasons are the
deterministic scorer's own evidence — an LLM never invents a justification (F27). Owner access; a
foreign enquiry/item is NOT_FOUND.

Read through the shared :class:`ItemStateSource`; the DB-backed store is not configured here, so a
clean 503 is surfaced. Thin, injectable adapter.
"""
from __future__ import annotations

from uuid import UUID

from partsiq.core.api_models import ExplanationView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.features.f20_machine_identification import ItemStateSource, require_item_state


async def explain_selection(
    actor: ActorContext,
    enquiry_id: UUID,
    item_id: UUID,
    *,
    container: AppContainer,
    source: ItemStateSource | None = None,
) -> ExplanationView:
    """Return the selection explanation (reasons + source reference) for one item (owner)."""
    source = source or require_item_state(container)
    return await source.read_explanation(actor, enquiry_id, item_id)
