"""F05 HTTP adapter: POST /v1/demo/sessions/{session_id}/reset (201).

Reset bumps the session generation and is idempotent per ``Idempotency-Key`` (required for every
mutating request). The body is :class:`RevisionOnly`; the caller may only reset its own session.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.auth.demo import DemoStore
from partsiq.core.api_models import RevisionOnly
from partsiq.core.contracts import ActorContext, DemoSession
from partsiq.core.dependencies import (
    AppContainer,
    get_container,
    idempotency_key,
    require_actor,
    typed_body,
)
from partsiq.core.errors import PartsIQError
from partsiq.features import f05_demo_reset as facade

router = APIRouter(tags=["demo"])


def _demo_store(container: AppContainer) -> DemoStore:
    store = container.demo_store
    if store is None:
        raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="demo store not configured")
    return store  # type: ignore[return-value]


@router.post(
    "/demo/sessions/{session_id}/reset",
    response_model=DemoSession,
    status_code=201,
    operation_id="f05_reset_session",
    summary="Reset the caller's demo session (bumps generation)",
)
async def reset_session(
    session_id: UUID,
    _body: RevisionOnly = Depends(typed_body(RevisionOnly)),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
    key: UUID = Depends(idempotency_key),
) -> DemoSession:
    return await facade.reset_session(actor, session_id, key, store=_demo_store(container))
