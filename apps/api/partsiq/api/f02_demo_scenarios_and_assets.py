"""F02 HTTP adapter: GET /v1/demo/scenarios.

Thin route adapter following the established pattern: resolve a verified actor
(``Depends(require_actor)``) and the container (``Depends(get_container)``), call the feature
facade exactly once, and return the declared response model. ``PartsIQError`` → RFC9457 Problem
is handled centrally in ``main.py``; the route raises, it never builds a Problem itself.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from partsiq.core.api_models import ScenarioList
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor
from partsiq.features import f02_demo_scenarios_and_assets as facade

router = APIRouter(tags=["demo"])


@router.get(
    "/demo/scenarios",
    response_model=ScenarioList,
    status_code=200,
    operation_id="f02_list_scenarios",
    summary="List the synthetic demo scenarios (demo access)",
)
async def list_scenarios(
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> ScenarioList:
    return facade.list_scenarios(actor, container=container)
