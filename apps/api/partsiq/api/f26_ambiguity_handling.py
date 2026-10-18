"""F26 HTTP adapter: POST /v1/enquiries/{enquiry_id}/items/{item_id}/choice (202).

A reviewer resolves an AMBIGUOUS ranking (F25) by choosing one candidate for an item. This is a
mutating correction: it carries an ``Idempotency-Key`` and an ``expected_revision`` (a stale choice
is a 409), and only a ``part_id`` already in the item's COMPATIBLE candidate set is accepted — the
F22 gate is never bypassed by a choice. Owner access; a foreign enquiry/item is NOT_FOUND.
Delegates to the ``f26_ambiguity_handling`` facade, which surfaces a clean 503 offline.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import CandidateChoice
from partsiq.core.contracts import ActorContext, EnquiryView
from partsiq.core.dependencies import (
    AppContainer,
    get_container,
    idempotency_key,
    require_actor,
    typed_body,
)
from partsiq.features import f26_ambiguity_handling as facade

router = APIRouter(tags=["search"])


@router.post(
    "/enquiries/{enquiry_id}/items/{item_id}/choice",
    response_model=EnquiryView,
    status_code=202,
    operation_id="f26_choose_candidate",
    summary="Choose a compatible candidate for an ambiguous enquiry item",
)
async def choose_candidate(
    enquiry_id: UUID,
    item_id: UUID,
    choice: CandidateChoice = Depends(typed_body(CandidateChoice)),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
    key: UUID = Depends(idempotency_key),
) -> EnquiryView:
    return await facade.choose_candidate(
        actor, enquiry_id, item_id, choice, key, container=container
    )
