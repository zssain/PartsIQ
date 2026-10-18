"""F23 HTTP adapter: GET /v1/enquiries/{enquiry_id}/items/{item_id}/match-evidence (200).

Returns the lexical match evidence (normalised query, matched aliases, removed machine terms) for
one item. Review access; a foreign enquiry/item is NOT_FOUND. Delegates to the
``f23_aliases_and_typo_matching`` facade.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import MatchEvidenceView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f23_aliases_and_typo_matching as facade

router = APIRouter(tags=["search"])


@router.get(
    "/enquiries/{enquiry_id}/items/{item_id}/match-evidence",
    response_model=MatchEvidenceView,
    status_code=200,
    operation_id="f23_lexical_evidence",
    summary="Read the lexical match evidence for an enquiry item",
)
async def lexical_evidence(
    enquiry_id: UUID,
    item_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> MatchEvidenceView:
    return await facade.lexical_evidence(actor, enquiry_id, item_id, container=container)
