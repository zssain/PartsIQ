"""F58 HTTP adapters (catalogue imports), all under /v1/admin/imports:

* POST   /v1/admin/imports                   (201) stage a new import batch
* GET    /v1/admin/imports/{import_id}        (200) read the batch + dry-run report
* POST   /v1/admin/imports/{import_id}/upload (200) sign the import-file upload
* POST   /v1/admin/imports/{import_id}/validate (202) queue the dry-run validation

Catalogue-admin access; a reviewer or non-staff (demo) caller is refused by the facade's role gate
(403), so a public demo can neither create nor validate a real batch. Delegates to the
``f58_catalogue_imports`` facade, which surfaces a clean 503 offline.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import ImportCreate, ImportUpload, ImportView, JobView
from partsiq.core.contracts import ActorContext, UploadTicket
from partsiq.core.dependencies import (
    AppContainer,
    get_container,
    require_actor,
    typed_body,
)
from partsiq.features import f58_catalogue_imports as facade

router = APIRouter(tags=["admin"])


@router.post(
    "/admin/imports",
    response_model=ImportView,
    status_code=201,
    operation_id="f58_stage_import",
    summary="Stage a new catalogue import batch (catalogue-admin only)",
)
async def stage_import(
    request: ImportCreate = Depends(typed_body(ImportCreate)),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> ImportView:
    return await facade.stage_import(actor, request, container=container)


@router.get(
    "/admin/imports/{import_id}",
    response_model=ImportView,
    status_code=200,
    operation_id="f58_read_import",
    summary="Read an import batch and its dry-run report (catalogue-admin only)",
)
async def read_import(
    import_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> ImportView:
    return await facade.read_import(actor, import_id, container=container)


@router.post(
    "/admin/imports/{import_id}/upload",
    response_model=UploadTicket,
    status_code=200,
    operation_id="f58_sign_import_upload",
    summary="Sign the import-file upload to private storage (catalogue-admin only)",
)
async def sign_import_upload(
    import_id: UUID,
    request: ImportUpload = Depends(typed_body(ImportUpload)),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> UploadTicket:
    return await facade.sign_import_upload(actor, import_id, request, container=container)


@router.post(
    "/admin/imports/{import_id}/validate",
    response_model=JobView,
    status_code=202,
    operation_id="f58_validate_import",
    summary="Queue a dry-run validation of an import batch (catalogue-admin only)",
)
async def validate_import(
    import_id: UUID,
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> JobView:
    return await facade.validate_import(actor, import_id, container=container)
