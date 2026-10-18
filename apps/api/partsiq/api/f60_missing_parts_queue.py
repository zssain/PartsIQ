"""F60 HTTP adapters (missing-parts queue):

* PATCH /v1/staff/missing-parts/{item_id} (200) transition a queue item with a mandatory note
* GET   /v1/staff/missing-parts            (200) list the reviewer's scoped queue (paginated)

``update_missing`` carries a :class:`MissingUpdate` (``expected_revision`` + state + required
note); resolving requires an explanation and a stale revision is a 409. ``list_missing`` validates
the inbox filters as QUERY params. Review/reviewer access; a non-staff (demo) caller is refused by
the facade's role gate (403), and a foreign item is NOT_FOUND. Delegates to the
``f60_missing_parts_queue`` facade, which surfaces a clean 503 offline.
"""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from partsiq.core.api_models import InboxQuery, MissingPage, MissingUpdate, MissingView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor, typed_body
from partsiq.features import f60_missing_parts_queue as facade

router = APIRouter(tags=["staff"])


@router.patch(
    "/staff/missing-parts/{item_id}",
    response_model=MissingView,
    status_code=200,
    operation_id="f60_update_missing",
    summary="Transition a missing-parts item with a mandatory note (resolve needs an explanation)",
)
async def update_missing(
    item_id: UUID,
    update: MissingUpdate = Depends(typed_body(MissingUpdate)),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> MissingView:
    return await facade.update_missing(actor, item_id, update, container=container)


@router.get(
    "/staff/missing-parts",
    response_model=MissingPage,
    status_code=200,
    operation_id="f60_list_missing",
    summary="List the reviewer's scoped missing-parts queue (paginated)",
)
async def list_missing(
    limit: int = Query(default=25, ge=1, le=100),
    cursor: str | None = Query(default=None),
    status: str | None = Query(default=None),
    priority: Literal["normal", "urgent"] | None = Query(default=None),
    overdue: bool = Query(default=False),
    query: str | None = Query(default=None, max_length=200),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> MissingPage:
    inbox_query = InboxQuery(
        cursor=cursor,
        limit=limit,
        status=status,
        priority=priority,
        overdue=overdue,
        query=query,
    )
    return await facade.list_missing(actor, inbox_query, container=container)
