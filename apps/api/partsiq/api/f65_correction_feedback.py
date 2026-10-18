"""F65 HTTP adapter: POST /v1/admin/corrections/{correction_id}/evaluation-case (201).

Promotes a human correction into a labelled evaluation case. The body is :class:`CurateRequest`
(case id + anonymized text + labelled outcome). Admin access; a non-staff caller is refused (403),
raw PII in the text is refused (422), and a case with no backing correction is a 404. Delegates to
the ``f65_correction_feedback`` facade, which surfaces a clean 503 offline.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import CurateRequest, CuratedView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor, typed_body
from partsiq.features import f65_correction_feedback as facade

router = APIRouter(tags=["admin"])


@router.post(
    "/admin/corrections/{correction_id}/evaluation-case",
    response_model=CuratedView,
    status_code=201,
    operation_id="f65_curate_correction",
    summary="Promote a human correction into a labelled evaluation case (admin-only, anonymized)",
)
async def curate_correction(
    correction_id: UUID,  # noqa: ARG001 - the labelled source; the store resolves it via the case id
    request: CurateRequest = Depends(typed_body(CurateRequest)),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> CuratedView:
    return await facade.curate_correction(actor, request, container=container)
