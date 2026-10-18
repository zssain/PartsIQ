"""F28 Compatibility references facade (helper ``evidence.list_references``).

Returns the catalogue evidence references that back an item's selected fitment: each reference is a
source citation (``source_reference``) and page, flagged ``synthetic`` when it comes from the
seed-42 fixture so a demo citation is never mistaken for a real document. Owner access; a foreign
enquiry/item is NOT_FOUND.

Read through the shared :class:`ItemStateSource`; the DB-backed store is not configured here, so a
clean 503 is surfaced. Thin, injectable adapter.
"""
from __future__ import annotations

from uuid import UUID

from partsiq.core.api_models import ReferenceList
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.features.f20_machine_identification import ItemStateSource, require_item_state


async def list_references(
    actor: ActorContext,
    enquiry_id: UUID,
    item_id: UUID,
    *,
    container: AppContainer,
    source: ItemStateSource | None = None,
) -> ReferenceList:
    """Return the catalogue evidence references backing one item's fitment (owner access)."""
    source = source or require_item_state(container)
    return await source.read_references(actor, enquiry_id, item_id)
