"""F22 Compatibility gate facade (helper ``search.compatible_set``).

Returns the compatible part set for an item's RESOLVED configuration: the part ids that are
explicitly listed as fitting that machine configuration in the active catalogue, together with the
catalogue version they came from. This is the compatibility gate that every downstream candidate
must pass — compatibility comes ONLY from the catalogue and an LLM never decides it (F22). Review
access; a foreign enquiry/item is NOT_FOUND, and an item whose identity is not yet resolved has no
compatible set to report.

Read through the shared :class:`ItemStateSource`; the DB-backed store is not configured here, so a
clean 503 is surfaced rather than a fabricated set. Thin, injectable adapter.
"""
from __future__ import annotations

from uuid import UUID

from partsiq.core.api_models import CompatibilityView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.features.f20_machine_identification import ItemStateSource, require_item_state


async def compatible_set(
    actor: ActorContext,
    enquiry_id: UUID,
    item_id: UUID,
    *,
    container: AppContainer,
    source: ItemStateSource | None = None,
) -> CompatibilityView:
    """Return the catalogue-derived compatible part set for one item's configuration (review)."""
    source = source or require_item_state(container)
    return await source.read_compatibility(actor, enquiry_id, item_id)
