"""F45 HTTP adapter: PUT /v1/staff/enquiries/{enquiry_id}/draft (200).

A reviewer saves the edited reply-slots draft; the save re-renders the preview and re-runs
verification, and never publishes. The body is :class:`DraftEdit` (``expected_revision`` + slots)
and the request carries an ``Idempotency-Key``; an ``expected_revision`` mismatch is a 409. Review
access; a foreign/unassigned enquiry is NOT_FOUND and a non-staff (demo) caller is refused by the
facade's role gate (403). Delegates to the ``f45_reply_drafting`` facade.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import DraftEdit, DraftView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import (
    AppContainer,
    get_container,
    idempotency_key,
    require_actor,
    typed_body,
)
from partsiq.features import f45_reply_drafting as facade

router = APIRouter(tags=["staff"])


@router.put(
    "/staff/enquiries/{enquiry_id}/draft",
    response_model=DraftView,
    status_code=200,
    operation_id="f45_save_slots",
    summary="Save the edited reply-slots draft (re-renders and re-verifies; never publishes)",
)
async def save_slots(
    enquiry_id: UUID,
    edit: DraftEdit = Depends(typed_body(DraftEdit)),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
    key: UUID = Depends(idempotency_key),
) -> DraftView:
    return await facade.save_slots(actor, enquiry_id, edit, key, container=container)
