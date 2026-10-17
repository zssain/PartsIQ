"""F58 gateway import adapter (owner: gateway).

Staff upload an import file; the gateway records an import_batches row and QUEUES a dry-run
validation job to the worker (which holds the catalogue role) — it never parses or publishes
inline. A public demo may inspect a supplied sample validation report but cannot create or
validate a real batch (that requires catalogue_admin/admin). Explicit publication calls F59
only after a batch reaches ``valid`` status.

The gateway stays decoupled from the worker's parser: it carries ids and surfaces the
worker-produced report as-is. The control port is injected; with none wired routes fail
closed (503). BLOCKED here.
"""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from partsiq_common.contracts import ActorContext, Contract
from partsiq_common.errors import PartsIQError

MAX_BYTES = 10 * 1024 * 1024
_PUBLISHER_ROLES = frozenset({"catalogue_admin", "admin"})


class CreateImportBody(Contract):
    filename: str
    media_type: str
    size_bytes: int


class ImportControl(Protocol):
    async def create_batch(self, actor: ActorContext, body: CreateImportBody) -> UUID: ...

    async def get_report(self, actor: ActorContext, batch_id: UUID) -> dict | None: ...

    async def enqueue_validate(self, actor: ActorContext, batch_id: UUID) -> UUID: ...


def _authorize_admin(actor: ActorContext) -> None:
    if not (_PUBLISHER_ROLES & set(actor.roles)):
        raise PartsIQError("FORBIDDEN", internal_detail="catalogue import requires catalogue_admin/admin")


async def create_import(actor: ActorContext, body: CreateImportBody, *, control: ImportControl) -> dict:
    """Record a new import batch (admin only); enforce the 10 MiB ceiling before staging."""
    _authorize_admin(actor)
    if body.size_bytes > MAX_BYTES:
        raise PartsIQError("PAYLOAD_TOO_LARGE", internal_detail=f"import exceeds {MAX_BYTES} bytes")
    batch_id = await control.create_batch(actor, body)
    return {"batch_id": str(batch_id)}


async def get_import_report(actor: ActorContext, batch_id: UUID, *, control: ImportControl) -> dict:
    """Return the dry-run report for a batch; a demo may view only a supplied sample report."""
    report = await control.get_report(actor, batch_id)
    if report is None:
        raise PartsIQError("NOT_FOUND", internal_detail="import batch report not found")
    return report


async def request_validate(actor: ActorContext, batch_id: UUID, *, control: ImportControl) -> dict:
    """Queue a dry-run validation to the worker (admin only); never validates inline."""
    _authorize_admin(actor)
    job_id = await control.enqueue_validate(actor, batch_id)
    return {"job_id": str(job_id)}
