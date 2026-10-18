"""F30 HTTP adapter: GET /v1/catalogue/parts/{part_number}/supersession (200).

Resolves a quoted part number to its forward supersession chain + current terminal over the
active catalogue version. Customer access; an unknown number is 404. Delegates to the
``f30_old_part_numbers`` facade.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from partsiq.core.api_models import SupersessionView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f30_old_part_numbers as facade

router = APIRouter(tags=["catalogue"])


@router.get(
    "/catalogue/parts/{part_number}/supersession",
    response_model=SupersessionView,
    status_code=200,
    operation_id="f30_resolve_supersession",
    summary="Resolve a quoted part number to its supersession chain and current terminal",
)
async def resolve_supersession(
    part_number: str,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> SupersessionView:
    return await facade.resolve_supersession(actor, part_number, container=container)
