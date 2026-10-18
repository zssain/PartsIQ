"""F04 HTTP adapter: POST /v1/demo/sessions (201) and GET /v1/demo/sessions/{session_id} (200).

A demo session is created-or-resolved for the verified anonymous actor and may only ever be read
by its own owner. The injected demo store lives on the container (``container.demo_store``).
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.auth.demo import DemoStore
from partsiq.core.contracts import ActorContext, DemoSession
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.core.errors import PartsIQError
from partsiq.features import f04_demo_isolation as facade

router = APIRouter(tags=["demo"])


def _demo_store(container: AppContainer) -> DemoStore:
    store = container.demo_store
    if store is None:
        raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="demo store not configured")
    return store  # type: ignore[return-value]


@router.post(
    "/demo/sessions",
    response_model=DemoSession,
    status_code=201,
    operation_id="f04_create_session",
    summary="Create (or resolve) the caller's demo session",
)
async def create_session(
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> DemoSession:
    return await facade.create_session(actor, store=_demo_store(container))


@router.get(
    "/demo/sessions/{session_id}",
    response_model=DemoSession,
    status_code=200,
    operation_id="f04_require_demo_session",
    summary="Resolve the caller's own demo session by id",
)
async def require_demo_session(
    session_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> DemoSession:
    return await facade.require_demo_session(actor, session_id, store=_demo_store(container))
