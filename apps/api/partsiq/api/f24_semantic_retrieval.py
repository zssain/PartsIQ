"""F24 HTTP adapter: GET /v1/search/capabilities (200).

Reports lexical/semantic retrieval readiness and the active catalogue source/version. Customer
access; the report reveals no inventory. Delegates to the ``f24_semantic_retrieval`` facade.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from partsiq.core.api_models import SearchCapabilities
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f24_semantic_retrieval as facade

router = APIRouter(tags=["search"])


@router.get(
    "/search/capabilities",
    response_model=SearchCapabilities,
    status_code=200,
    operation_id="f24_capabilities",
    summary="Report lexical/semantic retrieval readiness and the active catalogue version",
)
async def capabilities(
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> SearchCapabilities:
    return await facade.capabilities(actor, container=container)
