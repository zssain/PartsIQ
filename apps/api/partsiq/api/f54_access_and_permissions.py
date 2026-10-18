"""F54 HTTP adapter: GET /v1/me (200).

Returns the caller's own resolved identity (subject id, server-trusted roles, ``is_anonymous``,
active demo session id), derived entirely from the verified actor. Customer access; it reveals
only the caller's own identity. Delegates to the ``f54_access_and_permissions`` facade.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from partsiq.core.api_models import IdentityView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f54_access_and_permissions as facade

router = APIRouter(tags=["identity"])


@router.get(
    "/me",
    response_model=IdentityView,
    status_code=200,
    operation_id="f54_identity",
    summary="Read the caller's own resolved identity and server-trusted roles",
)
async def identity(
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> IdentityView:
    return await facade.identity(actor, container=container)
