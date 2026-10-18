"""F27 HTTP adapter: GET /v1/enquiries/{enquiry_id}/items/{item_id}/explanation (200).

Returns the deterministic scorer's own reasons the selected candidate was offered for an item,
plus the catalogue ``source_reference`` backing the fitment and the catalogue version — an LLM
never invents a justification (F27). Owner access; a foreign enquiry/item is NOT_FOUND. Delegates
to the ``f27_match_explanations`` facade, which surfaces a clean 503 offline.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import ExplanationView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f27_match_explanations as facade

router = APIRouter(tags=["search"])


@router.get(
    "/enquiries/{enquiry_id}/items/{item_id}/explanation",
    response_model=ExplanationView,
    status_code=200,
    operation_id="f27_explain_selection",
    summary="Read why the selected candidate was offered for an enquiry item",
)
async def explain_selection(
    enquiry_id: UUID,
    item_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> ExplanationView:
    return await facade.explain_selection(actor, enquiry_id, item_id, container=container)
