"""F12 HTTP adapter: GET /v1/enquiries/{enquiry_id}/messages (200).

Lists the caller's own enquiry messages. The ``PageQuery`` fields (``cursor``, ``limit``) are
validated QUERY parameters, not a JSON body (REST_API.md). ``limit`` defaults 25 and caps 100.
Owner access; a foreign enquiry is NOT_FOUND.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from partsiq.core.api_models import MessagePage
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f12_conversation_memory as facade

router = APIRouter(tags=["enquiries"])


@router.get(
    "/enquiries/{enquiry_id}/messages",
    response_model=MessagePage,
    status_code=200,
    operation_id="f12_list_messages",
    summary="List the caller's own enquiry messages (paginated)",
)
async def list_messages(
    enquiry_id: UUID,
    limit: int = Query(default=25, ge=1, le=100),
    cursor: str | None = Query(default=None),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> MessagePage:
    # ``cursor`` is accepted for contract parity; the bounded fixture journey returns one page.
    _ = cursor
    return await facade.list_messages(actor, enquiry_id, limit=limit, container=container)
