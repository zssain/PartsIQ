"""F31 HTTP adapter: GET /v1/enquiries/{enquiry_id}/items/{item_id}/comparison (200).

Returns a side-by-side comparison of 2-3 chosen candidate parts for an item as a
:class:`CandidateList` restricted to the requested ``part_ids``. The ``ComparisonQuery`` fields are
validated QUERY parameters (repeated ``part_ids``), not a JSON body (REST_API.md). Only part ids
already in the item's COMPATIBLE candidate set may be compared, so the F22 gate is never bypassed;
the runner-up ``margin`` is preserved over the full ranked set (F25). Review access; a foreign
enquiry/item is NOT_FOUND. Delegates to the ``f31_candidate_comparison`` facade (clean 503 offline).
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from partsiq.core.api_models import CandidateList, ComparisonQuery
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f31_candidate_comparison as facade

router = APIRouter(tags=["search"])


@router.get(
    "/enquiries/{enquiry_id}/items/{item_id}/comparison",
    response_model=CandidateList,
    status_code=200,
    operation_id="f31_compare_candidates",
    summary="Compare 2-3 compatible candidates for an enquiry item side by side",
)
async def compare_candidates(
    enquiry_id: UUID,
    item_id: UUID,
    part_ids: list[int] = Query(min_length=2, max_length=3),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> CandidateList:
    query = ComparisonQuery(part_ids=part_ids)
    return await facade.compare_candidates(
        actor, enquiry_id, item_id, query, container=container
    )
