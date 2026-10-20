"""F58 Catalogue imports facade (helpers ``catalogue.stage_import`` / ``catalogue.read_import`` /
``catalogue.sign_import_upload`` / ``catalogue.validate_import``).

A catalogue admin stages an import file, uploads it to private storage, and queues a DRY-RUN
validation — the import is never parsed or published inline. Four surfaces:

  * ``stage_import`` records a new import batch (201); the 10 MiB ceiling is enforced by the
    ``ImportCreate`` contract itself before anything is staged.
  * ``read_import`` returns the batch's current state and the worker-produced dry-run report
    (row count + per-row issues) as-is (200).
  * ``sign_import_upload`` mints a one-shot signed URL to upload the file to private storage (200).
  * ``validate_import`` queues the dry-run validation job to the worker and returns the job handle
    (202). Validation only REPORTS; it never mutates the active catalogue.

Every surface requires the ``catalogue_admin`` (or ``admin``) role; a reviewer or non-staff caller
is refused with FORBIDDEN (403) before any batch is touched, so a public demo can never create or
validate a real batch. Thin adapter over an injected port; the live import pipeline is BLOCKED
offline, so an admin gets a clean 503 rather than a fabricated import.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from partsiq.core.api_models import ImportCreate, ImportUpload, ImportView, JobView
from partsiq.core.contracts import ActorContext, UploadTicket
from partsiq.core.dependencies import AppContainer
from partsiq.core.errors import PartsIQError
from partsiq.features._ops_ports import require_store

# Roles permitted to manage catalogue imports. A reviewer manages review, not the catalogue.
CATALOGUE_ADMIN_ROLES: tuple[str, ...] = ("catalogue_admin", "admin")


def require_catalogue_admin(actor: ActorContext) -> None:
    """Refuse a non catalogue-admin caller with FORBIDDEN before any batch is touched (403).

    Role comes only from the server-trusted ``actor.roles``; a demo caller has an empty role list
    and is refused, so a public demo can never create or validate a real catalogue batch.
    """
    # Capability model (ADR 0002): accounts need catalogue_admin/admin; a demo visitor may run
    # imports only inside its own disposable sandbox catalogue (never the shared one).
    from partsiq.auth.actors import has_capability

    if not has_capability(actor, "catalogue.import"):
        raise PartsIQError(
            "FORBIDDEN", internal_detail="catalogue import requires catalogue_admin or admin"
        )


@runtime_checkable
class ImportSource(Protocol):
    """Catalogue-admin import control port (stage/read/sign-upload/validate)."""

    async def stage_import(self, actor: ActorContext, request: ImportCreate) -> ImportView: ...

    async def read_import(self, actor: ActorContext, import_id: UUID) -> ImportView: ...

    async def sign_import_upload(
        self, actor: ActorContext, import_id: UUID, request: ImportUpload
    ) -> UploadTicket: ...

    async def validate_import(self, actor: ActorContext, import_id: UUID) -> JobView: ...


async def stage_import(
    actor: ActorContext,
    request: ImportCreate,
    *,
    container: AppContainer,
    source: ImportSource | None = None,
) -> ImportView:
    """Record a new import batch (catalogue-admin only); the size ceiling is contract-enforced."""
    require_catalogue_admin(actor)
    source = source or require_store(container, "catalogue_imports")
    return await source.stage_import(actor, request)


async def read_import(
    actor: ActorContext,
    import_id: UUID,
    *,
    container: AppContainer,
    source: ImportSource | None = None,
) -> ImportView:
    """Return the batch state and its dry-run report as-is (catalogue-admin only)."""
    require_catalogue_admin(actor)
    source = source or require_store(container, "catalogue_imports")
    return await source.read_import(actor, import_id)


async def sign_import_upload(
    actor: ActorContext,
    import_id: UUID,
    request: ImportUpload,
    *,
    container: AppContainer,
    source: ImportSource | None = None,
) -> UploadTicket:
    """Mint a one-shot signed URL to upload the import file to private storage (catalogue-admin)."""
    require_catalogue_admin(actor)
    source = source or require_store(container, "catalogue_imports")
    return await source.sign_import_upload(actor, import_id, request)


async def validate_import(
    actor: ActorContext,
    import_id: UUID,
    *,
    container: AppContainer,
    source: ImportSource | None = None,
) -> JobView:
    """Queue a DRY-RUN validation job to the worker; never validates inline (catalogue-admin)."""
    require_catalogue_admin(actor)
    source = source or require_store(container, "catalogue_imports")
    return await source.validate_import(actor, import_id)
