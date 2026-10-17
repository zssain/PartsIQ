"""F59 Catalogue versioning (owner: catalog; depends on 02, 05, 06).

publish_version takes a validated candidate catalogue version and makes it the single active
version: it snapshots the records canonically (numeric ids preserved, sorted, decimals as
strings) and hashes them, then — under a serializing publication lock in the store — performs a
compare-and-set from the caller's expected active version to the new one. The expected-active
check is what stops two concurrent publishers from leaving two active versions: the second
compare-and-set sees a changed active version and is rejected (CONFLICT), so exactly one
version is ever active. A failed publish leaves the active version unchanged (the store's
single transaction rolls back), and prior approvals keep their immutable evidence snapshot —
publication never rewrites history, it only adds a new version and flips the active pointer.

Pending enquiries built on the retired version are invalidated lazily: their next action
re-verifies and fails check_catalogue_version (STALE_CATALOGUE), so no cross-version plan can
be approved. Only catalogue_admin/admin may publish.

This module is pure over an injected PublicationStore; the live catalogue-role Postgres adapter
(advisory lock 710070, single transaction) is wired by the worker publish command and is
BLOCKED here.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from partsiq_common.contracts import ActorContext, Contract
from partsiq_common.errors import PartsIQError

_PUBLISHER_ROLES = frozenset({"catalogue_admin", "admin"})


class F59Request(Contract):
    version_id: UUID
    expected_active_version_id: UUID
    idempotency_key: UUID


class F59Result(Contract):
    version_id: UUID
    published_at: datetime
    record_count: int


@dataclass(frozen=True, slots=True)
class Snapshot:
    sha256: str
    record_count: int


@dataclass(frozen=True, slots=True)
class CandidateVersion:
    version_id: UUID
    records: tuple[dict, ...]  # validated catalogue rows; each carries a numeric "id"


@dataclass(frozen=True, slots=True)
class PublishedVersion:
    version_id: UUID
    published_at: datetime
    record_count: int
    snapshot_sha256: str


def canonical_snapshot(records: tuple[dict, ...] | list[dict]) -> Snapshot:
    """Deterministic SHA-256 over the records, numeric ids preserved and order-independent."""
    ordered = sorted(records, key=lambda row: row["id"])  # preserve (never renumber) numeric ids
    canonical = json.dumps(ordered, sort_keys=True, separators=(",", ":"), default=str)
    return Snapshot(sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(), record_count=len(ordered))


class PublicationStore(Protocol):
    async def load_candidate(self, version_id: UUID) -> CandidateVersion | None: ...

    async def current_active_id(self) -> UUID | None: ...

    async def publish(
        self,
        actor: ActorContext,
        *,
        version_id: UUID,
        expected_active_id: UUID,
        snapshot: Snapshot,
        idempotency_key: UUID,
    ) -> PublishedVersion:
        """Under the publication lock: compare-and-set active from expected to version_id, atomically.

        Idempotent on idempotency_key. Raises CONFLICT if the active version is no longer
        ``expected_active_id`` (another publisher won the race). On any failure the active
        version is left unchanged.
        """
        ...


def _authorize(actor: ActorContext) -> None:
    if not (_PUBLISHER_ROLES & set(actor.roles)):
        raise PartsIQError("FORBIDDEN", internal_detail="catalogue publication requires catalogue_admin/admin")


async def publish_version(actor: ActorContext, request: F59Request, *, store: PublicationStore) -> F59Result:
    """Publish a validated candidate as the single active catalogue version."""
    _authorize(actor)
    candidate = await store.load_candidate(request.version_id)
    if candidate is None:
        raise PartsIQError("NOT_FOUND", internal_detail="candidate version not found")
    active = await store.current_active_id()
    if active != request.expected_active_version_id:
        # Optimistic concurrency: the caller's view of the active version is stale.
        raise PartsIQError("CONFLICT", internal_detail="active catalogue version changed; re-read and retry")
    snapshot = canonical_snapshot(candidate.records)
    published = await store.publish(
        actor,
        version_id=request.version_id,
        expected_active_id=request.expected_active_version_id,
        snapshot=snapshot,
        idempotency_key=request.idempotency_key,
    )
    return F59Result(
        version_id=published.version_id,
        published_at=published.published_at,
        record_count=published.record_count,
    )
