"""Atomic activation of a validated catalogue snapshot into the PostgreSQL serving cache.

Foundation 03. Snowflake (or the fixture source) owns the immutable source records for a
catalogue version; PostgreSQL owns the single *active* serving pointer (DATA_OWNERSHIP,
ARCHITECTURE section 5). Activation copies a VALIDATED
:class:`~partsiq.core.api_models.CatalogueSnapshot` into the ``catalogue_records`` serving
cache and atomically flips the active-catalogue pointer inside ONE transaction. It is an
explicit replicated-data contract, not two writable masters.

Ordering is fixed and strict (DATA_OWNERSHIP steps 6-7):

1. Validate the complete snapshot with :func:`partsiq.catalogue.validation.validate_snapshot`
   OUTSIDE any database lock. An invalid snapshot raises ``VALIDATION_FAILED`` and never
   activates — no partial write survives.
2. Acquire the catalogue advisory transaction lock so two publishers serialise.
3. Compare the caller's ``expected_active`` against the version currently published
   (compare-and-set). A stale expectation raises ``CONFLICT`` and the transaction rolls back,
   leaving exactly one active version untouched. The database-side partial unique index
   ``catalogue_one_published_idx`` is the backstop that guarantees the single-active invariant
   even if the application check were bypassed.
4. Upsert the immutable serving-cache rows (``catalogue_records``) for the version. Historical
   rows for other versions are never deleted; search reads filter on the active version keyset.
5. Retire the previously published version and publish the new one in the SAME transaction.
6. Write ONE audit record and the ``catalogue_syncs`` receipt in the SAME transaction.

Persistence happens exclusively through an injected :class:`ActivationPort` (an asyncpg
implementation at runtime, an in-memory fake in tests). This module never holds a
migration-owner credential and performs no Snowflake or network I/O while the lock is held.
If the transaction fails for any reason the previously active version remains active and the
remote version stays unactivated, safe to reconcile.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from partsiq.core.api_models import CatalogueSnapshot, SyncReceipt
from partsiq.core.errors import PartsIQError

from .models import content_sha256
from .validation import validate_snapshot

# Advisory lock key shared by every publisher so activations serialise cluster-wide. A single
# constant means two concurrent publishers always contend for the same lock, never two.
CATALOGUE_ACTIVATION_LOCK = 710070


class ActivationConflict(PartsIQError):
    """The expected active pointer did not match the version currently published."""

    def __init__(self, detail: str, *, internal_detail: str | None = None) -> None:
        super().__init__("CONFLICT", detail=detail, internal_detail=internal_detail)


class SnapshotInvalid(PartsIQError):
    """The snapshot failed pre-activation validation; it is never copied or published."""

    def __init__(self, detail: str, *, internal_detail: str | None = None) -> None:
        super().__init__("VALIDATION_FAILED", detail=detail, internal_detail=internal_detail)


@runtime_checkable
class ActivationPort(Protocol):
    """The persistence boundary for one activation, scoped to a single transaction.

    A concrete asyncpg implementation binds every method to one connection inside an open
    transaction (``Database.request_scope`` with the ``catalogue`` publisher role). All methods
    either all commit together or all roll back together — the caller never commits mid-way.
    Tests supply an in-memory fake that mirrors the compare-and-set and single-active-version
    constraint so the ordering contract is exercised without a live database.
    """

    async def acquire_lock(self, key: int) -> None:
        """Take the catalogue advisory transaction lock (``pg_advisory_xact_lock``)."""
        ...

    async def current_active_version(self) -> UUID | None:
        """Return the id of the version currently published, or ``None`` if none is."""
        ...

    async def upsert_records(self, snapshot: CatalogueSnapshot) -> int:
        """Materialise the serving-cache rows for the snapshot; return the row count written."""
        ...

    async def retire_active(self, version_id: UUID) -> None:
        """Retire the previously published version (sets state ``retired``)."""
        ...

    async def publish_version(self, snapshot: CatalogueSnapshot) -> None:
        """Mark ``snapshot.version_id`` published — the single active pointer."""
        ...

    async def write_audit(
        self, *, version_id: UUID, action: str, actor_id: str, payload: dict[str, object]
    ) -> None:
        """Append an immutable audit row for this activation in the same transaction."""
        ...

    async def write_sync_receipt(self, receipt: SyncReceipt) -> None:
        """Persist the activation ``catalogue_syncs`` receipt in the same transaction."""
        ...


async def activate_version(
    port: ActivationPort,
    snapshot: CatalogueSnapshot,
    expected_active: UUID | None,
    *,
    actor_id: str,
) -> SyncReceipt:
    """Validate, copy and atomically activate ``snapshot`` as the single active catalogue.

    ``expected_active`` is the version the caller believes is currently published (``None`` if
    the caller expects no active version yet). Activation is a compare-and-set: if the real
    current pointer differs, :class:`ActivationConflict` (HTTP 409) is raised and nothing is
    published. Validation runs first and outside the lock; an invalid snapshot raises
    :class:`SnapshotInvalid` (HTTP 422) and is never copied or published.

    Returns the :class:`SyncReceipt` describing the activated version. On any failure the port's
    transaction rolls back, so the previously active version remains active and no audit or
    serving-cache row is left behind.
    """
    # 1. Validate the complete version outside the database lock. A bad snapshot never activates.
    issues = validate_snapshot(snapshot)
    if issues:
        raise SnapshotInvalid(
            "Catalogue snapshot failed validation and was not activated.",
            internal_detail=f"{len(issues)} validation issue(s) in version {snapshot.version_id}",
        )

    # The manifest digest must match the records actually present (guards a truncated/altered
    # snapshot). This is a content check, not a reason to activate a never-validated version.
    recomputed = content_sha256(snapshot.records)
    if recomputed != snapshot.content_sha256:
        raise SnapshotInvalid(
            "Catalogue snapshot digest did not match its records and was not activated.",
            internal_detail=(
                f"expected {snapshot.content_sha256} computed {recomputed} "
                f"for version {snapshot.version_id}"
            ),
        )

    # 2. Serialise publishers on the catalogue advisory lock before reading the pointer.
    await port.acquire_lock(CATALOGUE_ACTIVATION_LOCK)

    # 3. Compare-and-set on the EXPECTED current pointer so two publishers cannot each believe
    #    they won and leave two active versions.
    current = await port.current_active_version()
    if current != expected_active:
        raise ActivationConflict(
            "The active catalogue version changed; reload and retry the activation.",
            internal_detail=f"expected active {expected_active} but found {current}",
        )

    # 4. Materialise the immutable serving-cache rows for this version (historical rows kept).
    record_count = await port.upsert_records(snapshot)

    # 5. Retire the old pointer and publish the new version in the same transaction.
    if current is not None:
        await port.retire_active(current)
    await port.publish_version(snapshot)

    receipt = SyncReceipt(
        version_id=snapshot.version_id,
        state="activated",
        record_count=record_count,
        content_sha256=snapshot.content_sha256,
        query_id=None,
    )

    # 6. Every irreversible mutation writes an audit record and the sync receipt in THIS
    #    transaction; a rollback discards all three together.
    await port.write_audit(
        version_id=snapshot.version_id,
        action="catalogue.activated",
        actor_id=actor_id,
        payload={
            "version_id": str(snapshot.version_id),
            "previous_version_id": str(current) if current is not None else None,
            "source": snapshot.source,
            "content_sha256": snapshot.content_sha256,
            "record_count": record_count,
        },
    )
    await port.write_sync_receipt(receipt)

    return receipt
