"""F49 HTTP adapter: GET /v1/staff/enquiries/{enquiry_id}/audit (200).

Returns the enquiry's append-only audit events in stable append order, keyset-paged. The
``PageQuery`` fields are validated QUERY parameters. Review access; a foreign/unassigned enquiry is
NOT_FOUND and a non-staff (demo) caller is refused by the facade's role gate (403). Delegates to
the ``f49_audit_trail`` facade.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from partsiq.core.api_models import AuditPage, PageQuery
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f49_audit_trail as facade

router = APIRouter(tags=["staff"])


@router.get(
    "/staff/enquiries/{enquiry_id}/audit",
    response_model=AuditPage,
    status_code=200,
    operation_id="f49_list_events",
    summary="List the append-only audit events for an enquiry (paginated)",
)
async def list_events(
    enquiry_id: UUID,
    limit: int = Query(default=25, ge=1, le=100),
    cursor: str | None = Query(default=None),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> AuditPage:
    query = PageQuery(cursor=cursor, limit=limit)
    return await facade.list_events(actor, enquiry_id, query, container=container)
