"""F57 HTTP adapter: GET /v1/catalogue/parts (200) and GET /v1/catalogue/parts/{part_number} (200).

Read-only browse (filters + cursor paging) and single-part detail over the active published
catalogue version. Customer access; an unknown part number is 404. The ``CatalogueQuery`` fields
are validated QUERY parameters, not a JSON body. Delegates to the ``f57_catalogue_browser`` facade.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from partsiq.core.api_models import CataloguePage, CataloguePart, CatalogueQuery
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f57_catalogue_browser as facade

router = APIRouter(tags=["catalogue"])


@router.get(
    "/catalogue/parts",
    response_model=CataloguePage,
    status_code=200,
    operation_id="f57_browse",
    summary="Browse the active published catalogue (filters + pagination)",
)
async def browse(
    limit: int = Query(default=25, ge=1, le=100),
    cursor: str | None = Query(default=None),
    query: str | None = Query(default=None, max_length=200),
    model_id: int | None = Query(default=None),
    category: str | None = Query(default=None),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> CataloguePage:
    criteria = CatalogueQuery(
        cursor=cursor, limit=limit, query=query, model_id=model_id, category=category
    )
    return await facade.browse(actor, criteria, container=container)


@router.get(
    "/catalogue/parts/{part_number}",
    response_model=CataloguePart,
    status_code=200,
    operation_id="f57_get_part",
    summary="Read one published catalogue part by number",
)
async def get_part(
    part_number: str,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> CataloguePart:
    return await facade.get_part(actor, part_number, container=container)
