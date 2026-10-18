"""F25 Ranked candidates facade (helper ``search.rank_candidates``).

Returns the ranked candidate parts for an item: the compatible-only set scored and ordered, with
the runner-up ``margin`` computed over the FULL ranked set BEFORE the response limit, and
``ambiguous`` set when the top two are too close to separate automatically (F25). Candidates are
compatible-only (the F22 gate), a NaN score is rejected rather than ranked unpredictably, and no LLM
decides the ranking. Review access; a foreign enquiry/item is NOT_FOUND.

Read through the shared :class:`ItemStateSource`; the DB-backed store is not configured in this
environment, so a clean 503 is surfaced. Thin, injectable adapter.
"""
from __future__ import annotations

from uuid import UUID

from partsiq.core.api_models import CandidateList
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.features.f20_machine_identification import ItemStateSource, require_item_state


async def rank_candidates(
    actor: ActorContext,
    enquiry_id: UUID,
    item_id: UUID,
    *,
    container: AppContainer,
    source: ItemStateSource | None = None,
) -> CandidateList:
    """Return the ranked compatible candidate list for one item, with its margin (review)."""
    source = source or require_item_state(container)
    return await source.read_candidates(actor, enquiry_id, item_id)
