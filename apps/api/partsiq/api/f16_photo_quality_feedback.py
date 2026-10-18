"""F16 HTTP adapter: GET /v1/attachments/{attachment_id}/quality (200).

Returns the stored quality verdict for an uploaded nameplate attachment: a status, observed
dimensions and named, actionable retake WARNINGS the web maps to localised guidance. No fabricated
accuracy percentage is produced — confidence is never accuracy (ADR-013). Owner access; a foreign
attachment is NOT_FOUND. Delegates to the ``f16_photo_quality_feedback`` facade, which surfaces a
clean 503 offline (the stored verdict is DB-backed).
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import QualityView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f16_photo_quality_feedback as facade

router = APIRouter(tags=["enquiries"])


@router.get(
    "/attachments/{attachment_id}/quality",
    response_model=QualityView,
    status_code=200,
    operation_id="f16_read_quality",
    summary="Read the stored quality verdict for an uploaded nameplate attachment",
)
async def read_quality(
    attachment_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> QualityView:
    return await facade.read_quality(actor, attachment_id, container=container)
