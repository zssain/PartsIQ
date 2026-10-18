"""F64 HTTP adapters (AI allowance):

* GET /v1/admin/ai-allowance (200) read the manually-confirmed free-credit allowance
* PUT /v1/admin/ai-allowance (200) configure it (validated: no paid fallback, positive, future)

``configure_allowance`` carries an :class:`AllowanceSet`; an invalid allowance (non-zero paid
budget, non-positive amount or past expiry) is rejected before anything is persisted. Admin access;
a non-admin caller is refused by the facade's role gate (403). Delegates to the
``f64_latency_and_ai_cost`` facade, which surfaces a clean 503 offline.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from partsiq.core.api_models import AllowanceSet, AllowanceView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer, get_container, require_actor, typed_body
from partsiq.features import f64_latency_and_ai_cost as facade

router = APIRouter(tags=["admin"])


@router.get(
    "/admin/ai-allowance",
    response_model=AllowanceView,
    status_code=200,
    operation_id="f64_read_allowance",
    summary="Read the manually-confirmed AI credit allowance (admin-only)",
)
async def read_allowance(
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> AllowanceView:
    return await facade.read_allowance(actor, container=container)


@router.put(
    "/admin/ai-allowance",
    response_model=AllowanceView,
    status_code=200,
    operation_id="f64_configure_allowance",
    summary="Configure the AI credit allowance (admin-only; no paid fallback)",
)
async def configure_allowance(
    request: AllowanceSet = Depends(typed_body(AllowanceSet)),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> AllowanceView:
    return await facade.configure_allowance(actor, request, container=container)
