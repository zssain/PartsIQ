"""F36 HTTP adapter: GET /v1/staff/enquiries (200).

Lists the staff inbox within the caller's access scope (a reviewer sees only enquiries assigned to
them; an admin sees all), with status/priority/overdue/free-text filters and keyset pagination.
The ``InboxQuery`` fields are validated QUERY parameters, not a JSON body. Reviewer access; a
non-staff (demo) caller is refused by the facade's role gate (403). Delegates to the
``f36_staff_inbox`` facade.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query

from partsiq.core.api_models import EnquiryPage, InboxQuery
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f36_staff_inbox as facade

router = APIRouter(tags=["staff"])


@router.get(
    "/staff/enquiries",
    response_model=EnquiryPage,
    status_code=200,
    operation_id="f36_list_assigned",
    summary="List the staff inbox within the caller's access scope (paginated)",
)
async def list_assigned(
    limit: int = Query(default=25, ge=1, le=100),
    cursor: str | None = Query(default=None),
    status: str | None = Query(default=None),
    priority: Literal["normal", "urgent"] | None = Query(default=None),
    overdue: bool = Query(default=False),
    query: str | None = Query(default=None, max_length=200),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> EnquiryPage:
    inbox_query = InboxQuery(
        cursor=cursor,
        limit=limit,
        status=status,
        priority=priority,
        overdue=overdue,
        query=query,
    )
    return await facade.list_assigned(actor, inbox_query, container=container)
