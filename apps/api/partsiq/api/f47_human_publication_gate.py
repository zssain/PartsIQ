"""F47 HTTP adapter: GET /v1/enquiries/{enquiry_id}/published-reply (200).

Returns the ONE approved recommendation the customer may see for their OWN enquiry (message +
decision id + approved revision), or the empty view when nothing has been approved yet — nothing
unapproved ever reaches the customer. Owner access; a foreign/stale enquiry is NOT_FOUND. Delegates
to the ``f47_human_publication_gate`` facade.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import PublishedView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f47_human_publication_gate as facade

router = APIRouter(tags=["enquiries"])


@router.get(
    "/enquiries/{enquiry_id}/published-reply",
    response_model=PublishedView,
    status_code=200,
    operation_id="f47_read_approved",
    summary="Read the caller's own approved recommendation (if any)",
)
async def read_approved(
    enquiry_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> PublishedView:
    return await facade.read_approved(actor, enquiry_id, container=container)
