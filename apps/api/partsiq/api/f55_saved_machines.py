"""F55 HTTP adapters: POST /v1/machines (201), GET /v1/machines (200), DELETE /v1/machines/{id} (200).

A customer saves a confirmed ``(model, serial)`` under a label (201), lists their own active
entries (200, keyset-paged via the ``PageQuery`` QUERY params), and archives one (200). Save
carries an ``Idempotency-Key``. Customer access; every operation is owner-scoped to the verified
actor, so a foreign id is NOT_FOUND. Delegates to the ``f55_saved_machines`` facade, which surfaces
a clean 503 offline.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from partsiq.core.api_models import ArchiveResult, MachinePage, MachineSave, PageQuery, SavedMachineView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import (
    AppContainer,
    get_container,
    idempotency_key,
    require_actor,
    typed_body,
)
from partsiq.features import f55_saved_machines as facade

router = APIRouter(tags=["machines"])


@router.post(
    "/machines",
    response_model=SavedMachineView,
    status_code=201,
    operation_id="f55_save",
    summary="Save a confirmed (model, serial) under a label (identifiers only)",
)
async def save(
    request: MachineSave = Depends(typed_body(MachineSave)),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
    key: UUID = Depends(idempotency_key),
) -> SavedMachineView:
    return await facade.save(actor, request, key, container=container)


@router.get(
    "/machines",
    response_model=MachinePage,
    status_code=200,
    operation_id="f55_list_owned",
    summary="List the caller's own active saved machines (paginated)",
)
async def list_owned(
    limit: int = Query(default=25, ge=1, le=100),
    cursor: str | None = Query(default=None),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> MachinePage:
    query = PageQuery(cursor=cursor, limit=limit)
    return await facade.list_owned(actor, query, container=container)


@router.delete(
    "/machines/{machine_id}",
    response_model=ArchiveResult,
    status_code=200,
    operation_id="f55_archive",
    summary="Archive the caller's own saved machine (soft delete)",
)
async def archive(
    machine_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> ArchiveResult:
    return await facade.archive(actor, machine_id, container=container)
