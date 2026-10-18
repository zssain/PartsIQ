"""F17 HTTP adapter: PATCH /v1/enquiries/{enquiry_id}/items (200).

Corrects an enquiry's items (1..20) as a single REVISION: locks the enquiry, checks
``expected_revision`` (a stale edit is a 409), increments the revision, snapshots immutably and
invalidates derived state so every item recomputes — stock is then planned once across combined
quantities per part, so duplicate lines never double-count (F17). A historical approval is never
mutated (F40). Mutating, so an ``Idempotency-Key`` is required. Owner access; a foreign enquiry is
NOT_FOUND. The response is the committed new-revision :class:`EnquiryView` (200). Delegates to the
``f17_multi_part_enquiries`` facade, which surfaces a clean 503 offline.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import ItemsEdit
from partsiq.core.contracts import ActorContext, EnquiryView
from partsiq.core.dependencies import (
    AppContainer,
    get_container,
    idempotency_key,
    require_actor,
    typed_body,
)
from partsiq.features import f17_multi_part_enquiries as facade

router = APIRouter(tags=["enquiries"])


@router.patch(
    "/enquiries/{enquiry_id}/items",
    response_model=EnquiryView,
    status_code=200,
    operation_id="f17_correct_items",
    summary="Correct an enquiry's items as a single revision",
)
async def correct_items(
    enquiry_id: UUID,
    command: ItemsEdit = Depends(typed_body(ItemsEdit)),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
    key: UUID = Depends(idempotency_key),
) -> EnquiryView:
    # ``key`` enforces the Idempotency-Key header (REST_API.md); the DB-backed correction
    # transaction is idempotent per key once wired.
    _ = key
    return await facade.correct_items(actor, enquiry_id, command, container=container)
