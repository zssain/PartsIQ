"""F31 Candidate comparison facade (helper ``search.compare_candidates``).

Returns a side-by-side comparison of 2-3 chosen candidate parts for an item, as a
:class:`CandidateList` restricted to the requested ``part_ids``. Only part ids that are already in
the item's COMPATIBLE candidate set may be compared — a part outside the catalogue-derived
compatible set is rejected, so the F22 gate is never bypassed by a comparison request. The
runner-up ``margin`` is preserved over the full ranked set (F25). Review access; a foreign
enquiry/item is NOT_FOUND.

Read through the shared :class:`ItemStateSource`; the DB-backed store is not configured here, so a
clean 503 is surfaced. Thin, injectable adapter.
"""
from __future__ import annotations

from uuid import UUID

from partsiq.core.api_models import CandidateList, ComparisonQuery
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.features.f20_machine_identification import ItemStateSource, require_item_state


async def compare_candidates(
    actor: ActorContext,
    enquiry_id: UUID,
    item_id: UUID,
    query: ComparisonQuery,
    *,
    container: AppContainer,
    source: ItemStateSource | None = None,
) -> CandidateList:
    """Compare 2-3 compatible candidates for one item, restricted to the requested ids (review)."""
    source = source or require_item_state(container)
    return await source.compare_candidates(actor, enquiry_id, item_id, list(query.part_ids))
