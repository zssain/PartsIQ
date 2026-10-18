"""F19 HTTP adapter: GET /v1/enquiries (200).

Lists the caller's OWN enquiry history, newest-first, keyset-paginated. The ``HistoryQuery`` fields
(``cursor``, ``limit``, ``status``) are validated QUERY parameters, not a JSON body (REST_API.md).
``limit`` defaults 25 and caps 100. Customer access; ownership is derived from the verified actor.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from partsiq.core.api_models import EnquiryPage, HistoryQuery
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f19_enquiry_history as facade

router = APIRouter(tags=["enquiries"])


@router.get(
    "/enquiries",
    response_model=EnquiryPage,
    status_code=200,
    operation_id="f19_list_enquiries",
    summary="List the caller's own enquiry history (paginated)",
)
async def list_enquiries(
    limit: int = Query(default=25, ge=1, le=100),
    cursor: str | None = Query(default=None),
    status: str | None = Query(default=None),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> EnquiryPage:
    query = HistoryQuery(cursor=cursor, limit=limit, status=status)
    return await facade.list_enquiries(actor, query, container=container)
