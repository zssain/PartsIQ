"""F62 HTTP adapters (labelled evaluations):

* POST /v1/admin/evaluations          (202) queue a labelled evaluation run
* GET  /v1/admin/evaluations/{run_id} (200) read a run's state and per-case results

``enqueue_run`` carries an :class:`EvalRequest` (suite + include_demo) and an ``Idempotency-Key``.
Admin access; any other (or anonymous) caller is refused by the facade's role gate (403). Delegates
to the ``f62_labelled_evaluations`` facade, which surfaces a clean 503 offline.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import EvalRequest, EvaluationView, JobView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import (
    AppContainer,
    get_container,
    idempotency_key,
    require_actor,
    typed_body,
)
from partsiq.features import f62_labelled_evaluations as facade

router = APIRouter(tags=["admin"])


@router.post(
    "/admin/evaluations",
    response_model=JobView,
    status_code=202,
    operation_id="f62_enqueue_run",
    summary="Queue a labelled evaluation run (admin-only)",
)
async def enqueue_run(
    request: EvalRequest = Depends(typed_body(EvalRequest)),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
    key: UUID = Depends(idempotency_key),
) -> JobView:
    return await facade.enqueue_run(actor, request, key, container=container)


@router.get(
    "/admin/evaluations/{run_id}",
    response_model=EvaluationView,
    status_code=200,
    operation_id="f62_read_run",
    summary="Read a labelled evaluation run (admin-only)",
)
async def read_run(
    run_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> EvaluationView:
    return await facade.read_run(actor, run_id, container=container)
