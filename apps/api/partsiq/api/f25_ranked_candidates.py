"""F25 HTTP adapter: GET /v1/enquiries/{enquiry_id}/items/{item_id}/candidates (200).

Returns the ranked compatible candidate list for one item, with the runner-up margin and the
ambiguity flag. Review access; a foreign enquiry/item is NOT_FOUND. Delegates to the
``f25_ranked_candidates`` facade.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import CandidateList
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f25_ranked_candidates as facade

router = APIRouter(tags=["search"])


@router.get(
    "/enquiries/{enquiry_id}/items/{item_id}/candidates",
    response_model=CandidateList,
    status_code=200,
    operation_id="f25_rank_candidates",
    summary="Read the ranked compatible candidate list for an enquiry item",
)
async def rank_candidates(
    enquiry_id: UUID,
    item_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> CandidateList:
    return await facade.rank_candidates(actor, enquiry_id, item_id, container=container)
