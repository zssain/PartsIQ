"""F59 HTTP adapters (catalogue versioning):

* POST /v1/admin/imports/{import_id}/publish (202) queue the compare-and-set publish
* GET  /v1/admin/catalogue/versions          (200) list every catalogue version

``publish`` carries a :class:`PublishRequest` (``content_sha256`` + ``expected_active_version_id``)
and an ``Idempotency-Key``; the switch is single-winner compare-and-set (a stale active version is
a 409) and runs on the worker, never inline. Catalogue-admin access; a reviewer or non-staff caller
is refused by the facade's role gate (403). Delegates to the ``f59_catalogue_versioning`` facade,
which surfaces a clean 503 offline.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import JobView, PublishRequest, VersionList
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import (
    AppContainer,
    get_container,
    idempotency_key,
    require_actor,
    typed_body,
)
from partsiq.features import f59_catalogue_versioning as facade

router = APIRouter(tags=["admin"])


@router.post(
    "/admin/imports/{import_id}/publish",
    response_model=JobView,
    status_code=202,
    operation_id="f59_request_publish",
    summary="Publish a validated import as the active catalogue version (compare-and-set)",
)
async def request_publish(
    import_id: UUID,
    request: PublishRequest = Depends(typed_body(PublishRequest)),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
    key: UUID = Depends(idempotency_key),
) -> JobView:
    return await facade.request_publish(actor, import_id, request, key, container=container)


@router.get(
    "/admin/catalogue/versions",
    response_model=VersionList,
    status_code=200,
    operation_id="f59_list_versions",
    summary="List every catalogue version (catalogue-admin only)",
)
async def list_versions(
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
) -> VersionList:
    return await facade.list_versions(actor, container=container)
