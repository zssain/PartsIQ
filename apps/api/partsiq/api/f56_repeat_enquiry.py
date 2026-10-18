"""F56 HTTP adapter: POST /v1/enquiries/{enquiry_id}/repeat (202).

Re-asks a prior enquiry as a brand-new one (fresh id, revision 1) that copies only the original
request text + confirmed hints plus the supplied locale/destination, then runs the full pipeline
again — never pre-approved. The body is :class:`RepeatRequest` (locale + destination warehouse) and
the request carries an ``Idempotency-Key``. Owner access; a foreign source is NOT_FOUND. Delegates
to the ``f56_repeat_enquiry`` facade, which surfaces a clean 503 offline.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import RepeatRequest
from partsiq.core.contracts import ActorContext, EnquiryView
from partsiq.core.dependencies import (
    AppContainer,
    get_container,
    idempotency_key,
    require_actor,
    typed_body,
)
from partsiq.features import f56_repeat_enquiry as facade

router = APIRouter(tags=["enquiries"])


@router.post(
    "/enquiries/{enquiry_id}/repeat",
    response_model=EnquiryView,
    status_code=202,
    operation_id="f56_repeat_enquiry",
    summary="Repeat a prior enquiry as a fresh enquiry (copies text/hints only; never pre-approved)",
)
async def repeat_enquiry(
    enquiry_id: UUID,
    request: RepeatRequest = Depends(typed_body(RepeatRequest)),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
    key: UUID = Depends(idempotency_key),
) -> EnquiryView:
    return await facade.repeat_enquiry(actor, enquiry_id, request, key, container=container)
