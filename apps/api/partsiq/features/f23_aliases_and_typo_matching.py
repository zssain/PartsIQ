"""F23 Aliases and typo matching evidence facade (helper ``search.lexical_evidence``).

Returns the lexical match evidence for an item: the normalised query, the part aliases that
matched, and the machine terms that were removed before scoring (so the model code never drowns out
the words that say which PART is wanted). This exposes exactly what the deterministic lexical scorer
(:mod:`partsiq.search.lexical`) saw — no LLM is involved. Review access; a foreign enquiry/item is
NOT_FOUND.

Read through the shared :class:`ItemStateSource`; the DB-backed store is not configured in this
environment, so a clean 503 is surfaced. Thin, injectable adapter.
"""
from __future__ import annotations

from uuid import UUID

from partsiq.core.api_models import MatchEvidenceView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.features.f20_machine_identification import ItemStateSource, require_item_state


async def lexical_evidence(
    actor: ActorContext,
    enquiry_id: UUID,
    item_id: UUID,
    *,
    container: AppContainer,
    source: ItemStateSource | None = None,
) -> MatchEvidenceView:
    """Return the lexical match evidence for one enquiry item (review access)."""
    source = source or require_item_state(container)
    return await source.read_match_evidence(actor, enquiry_id, item_id)
