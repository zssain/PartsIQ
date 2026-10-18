"""F55 Saved machines facade (helpers ``machines.save`` / ``machines.list_owned`` /
``machines.archive``).

A customer saves a confirmed ``(model, serial)`` under a label, lists their own active entries, and
archives one (soft delete). Every operation is OWNER-SCOPED to the verified actor (and, for a demo,
the active session generation), so a foreign id is NOT_FOUND (404), never another customer's
machine — ownership is derived from the actor, never from a request field. A saved machine stores
only IDENTIFIERS; it never caches a configuration or candidate set, so reusing it later prefills a
NEW enquiry that re-identifies against the CURRENT catalogue rather than replaying a stale,
possibly-wrong guess as authoritative. Saving is idempotent on the request ``Idempotency-Key``.

Thin adapter over an injected port; the live DB adapter is BLOCKED offline, so the customer gets a
clean 503 rather than a fabricated save.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from partsiq.core.api_models import (
    ArchiveResult,
    MachinePage,
    MachineSave,
    PageQuery,
    SavedMachineView,
)
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.features._ops_ports import require_store


@runtime_checkable
class SavedMachineSource(Protocol):
    """Owner-scoped saved-machine port (identifiers only; no cached configuration)."""

    async def save(
        self, actor: ActorContext, request: MachineSave, key: UUID
    ) -> SavedMachineView: ...

    async def list_owned(self, actor: ActorContext, query: PageQuery) -> MachinePage: ...

    async def archive(self, actor: ActorContext, machine_id: UUID) -> ArchiveResult: ...


async def save(
    actor: ActorContext,
    request: MachineSave,
    key: UUID,
    *,
    container: AppContainer,
    source: SavedMachineSource | None = None,
) -> SavedMachineView:
    """Save a confirmed (model, serial) under a label; owner-scoped, idempotent on the key."""
    source = source or require_store(container, "saved_machines")
    return await source.save(actor, request, key)


async def list_owned(
    actor: ActorContext,
    query: PageQuery,
    *,
    container: AppContainer,
    source: SavedMachineSource | None = None,
) -> MachinePage:
    """List the caller's OWN active saved machines, keyset-paged."""
    source = source or require_store(container, "saved_machines")
    return await source.list_owned(actor, query)


async def archive(
    actor: ActorContext,
    machine_id: UUID,
    *,
    container: AppContainer,
    source: SavedMachineSource | None = None,
) -> ArchiveResult:
    """Soft-archive the caller's OWN machine; a foreign id is NOT_FOUND (never deletes data)."""
    source = source or require_store(container, "saved_machines")
    return await source.archive(actor, machine_id)
