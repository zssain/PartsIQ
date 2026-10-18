"""F59 Catalogue versioning facade (helpers ``catalogue.request_publish`` /
``catalogue.list_versions``).

A catalogue admin publishes a VALIDATED import as the new active catalogue version, and lists all
versions. Two surfaces:

  * ``request_publish`` queues a durable publish job to the worker (which holds the catalogue DB
    credential) and returns the job handle (202) — it never flips the active version inline. The
    switch is a COMPARE-AND-SET: the request carries ``expected_active_version_id`` and a
    ``content_sha256``, so two concurrent publishes cannot both win and a publish built on a stale
    active version is rejected (409). Exactly one version is active at any time; in-flight
    enquiries keep reading the version they started on (append-only versioning).
  * ``list_versions`` returns every version with its state, content hash, publish time and source
    (200), read-only.

Both require ``catalogue_admin`` (or ``admin``); a reviewer or non-staff caller is refused (403).
Thin adapter over an injected port; the live publish pipeline is BLOCKED offline, so an admin gets
a clean 503 rather than a fabricated version switch.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from partsiq.core.api_models import JobView, PublishRequest, VersionList
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.features._ops_ports import require_store
from partsiq.features.f58_catalogue_imports import require_catalogue_admin


@runtime_checkable
class VersioningSource(Protocol):
    """Catalogue-admin publish/list port (compare-and-set single-active publication)."""

    async def request_publish(
        self, actor: ActorContext, import_id: UUID, request: PublishRequest, key: UUID
    ) -> JobView: ...

    async def list_versions(self, actor: ActorContext) -> VersionList: ...


async def request_publish(
    actor: ActorContext,
    import_id: UUID,
    request: PublishRequest,
    key: UUID,
    *,
    container: AppContainer,
    source: VersioningSource | None = None,
) -> JobView:
    """Queue the compare-and-set publish of a validated import; never inline (catalogue-admin).

    The ``expected_active_version_id`` + ``content_sha256`` make the publish a single-winner
    compare-and-set; a stale active version is a 409. Idempotent on the request ``Idempotency-Key``.
    """
    require_catalogue_admin(actor)
    source = source or require_store(container, "catalogue_versions")
    return await source.request_publish(actor, import_id, request, key)


async def list_versions(
    actor: ActorContext,
    *,
    container: AppContainer,
    source: VersioningSource | None = None,
) -> VersionList:
    """List every catalogue version with its state and source (catalogue-admin; read-only)."""
    require_catalogue_admin(actor)
    source = source or require_store(container, "catalogue_versions")
    return await source.list_versions(actor)
