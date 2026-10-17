"""Foundation 03 acceptance: Supabase migrations, RLS/roles and atomic activation.

Two kinds of check live here, both OFFLINE and deterministic:

* Schema/infrastructure: the five build-kit migrations exist and contain the real objects the
  prompt names (RLS enabled, NOLOGIN group roles, the per-item candidate/revision keys, the
  single-active-version backstop, the immutable serving cache). These are asserted by reading
  the committed SQL text, not by mocking the check itself.
* Activation: :func:`partsiq.catalogue.activation.activate_version` validates then copies then
  flips the pointer atomically through an injected :class:`ActivationPort`. A deterministic
  in-memory fake mirrors the compare-and-set and the single-active-version constraint, and can
  fail at a chosen step so the all-or-nothing (rollback) contract is observable.

Live Postgres/Supabase is BLOCKED in this environment, so the one case that needs a real
database is marked SKIP (never faked) — see ``test_live_activation_roundtrip_blocked``.
"""
from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest

from partsiq.catalogue import activation as activation_mod
from partsiq.catalogue.activation import (
    CATALOGUE_ACTIVATION_LOCK,
    ActivationConflict,
    ActivationPort,
    SnapshotInvalid,
    activate_version,
)
from partsiq.catalogue.models import build_snapshot
from partsiq.core.api_models import CatalogueRecord, CatalogueSnapshot, SyncReceipt
from partsiq.core.errors import PartsIQError

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MIGRATIONS = _REPO_ROOT / "supabase" / "migrations"
_VERSION_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_VERSION_B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
_ACTOR = "00000000-0000-0000-0000-0000000000ff"

_TARGET_MIGRATIONS = (
    "001_initial_schema.sql",
    "002_search_and_fulfilment.sql",
    "003_application.sql",
    "004_rls.sql",
    "005_storage.sql",
)


def _read(name: str) -> str:
    return (_MIGRATIONS / name).read_text(encoding="utf-8")


# --- synthetic, VALID catalogue (mirrors the foundation 02 fixture shape) ------------------

def _valid_records() -> list[CatalogueRecord]:
    return [
        CatalogueRecord(entity_type="equipment_families", entity_key="EXC",
                        payload={"code": "EXC", "name_en": "Excavators", "name_ar": "حفارات"}),
        CatalogueRecord(entity_type="equipment_models", entity_key='["ACME","X9"]',
                        payload={"family_code": "EXC", "brand": "ACME", "model_code": "X9",
                                 "display_name": "ACME X9"}),
        CatalogueRecord(entity_type="model_configurations", entity_key='["ACME","X9","A"]',
                        payload={"brand": "ACME", "model_code": "X9", "config_code": "A",
                                 "serial_start": 1, "serial_end": 100}),
        CatalogueRecord(entity_type="parts", entity_key="101",
                        payload={"part_number": "FLT-101", "name_en": "Oil filter",
                                 "name_ar": "فلتر زيت", "category": "filters",
                                 "unit_of_measure": "ea", "is_active": True}),
        CatalogueRecord(entity_type="part_compatibility", entity_key='["101","ACME","X9","A"]',
                        payload={"part_number": "FLT-101", "brand": "ACME", "model_code": "X9",
                                 "config_code": "A", "quantity_per_unit": 1,
                                 "source_reference": "Manual p.12"}),
    ]


def _valid_snapshot(version_id: UUID = _VERSION_A) -> CatalogueSnapshot:
    return build_snapshot(version_id=version_id, source="fixture", records=_valid_records())


def _invalid_snapshot(version_id: UUID = _VERSION_A) -> CatalogueSnapshot:
    # Dangling compatibility reference to a part that is not present: validation must reject it.
    records = [
        CatalogueRecord(entity_type="part_compatibility", entity_key='["999","ACME","X9","A"]',
                        payload={"part_number": "NOPE-999", "brand": "ACME", "model_code": "X9",
                                 "config_code": "A", "quantity_per_unit": 1,
                                 "source_reference": "Manual p.12"}),
    ]
    return build_snapshot(version_id=version_id, source="fixture", records=records)


# --- in-memory activation port -------------------------------------------------------------

class FakeActivationPort:
    """Deterministic in-memory port mirroring the compare-and-set + single-active constraint.

    State is only committed to ``store`` when ``activate_version`` completes without raising;
    because the real port is one transaction, the fake buffers every mutation and applies it on
    :meth:`commit`. A chosen ``fail_on`` step raises so the rollback contract can be observed:
    nothing in ``store`` changes.
    """

    def __init__(self, store: "ActivationStore", *, fail_on: str | None = None) -> None:
        self._store = store
        self._fail_on = fail_on
        self.ops: list[str] = []
        # Staged (uncommitted) mutations:
        self._staged_records: tuple[UUID, int] | None = None
        self._staged_retire: UUID | None = None
        self._staged_publish: UUID | None = None
        self._staged_audit: dict[str, object] | None = None
        self._staged_receipt: SyncReceipt | None = None

    def _maybe_fail(self, step: str) -> None:
        if self._fail_on == step:
            raise RuntimeError(f"injected failure at {step}")

    async def acquire_lock(self, key: int) -> None:
        self.ops.append("acquire_lock")
        assert key == CATALOGUE_ACTIVATION_LOCK
        self._store.locked = True
        self._maybe_fail("acquire_lock")

    async def current_active_version(self) -> UUID | None:
        self.ops.append("current_active_version")
        return self._store.active

    async def upsert_records(self, snapshot: CatalogueSnapshot) -> int:
        self.ops.append("upsert_records")
        count = len(snapshot.records)
        self._staged_records = (snapshot.version_id, count)
        self._maybe_fail("upsert_records")
        return count

    async def retire_active(self, version_id: UUID) -> None:
        self.ops.append("retire_active")
        self._staged_retire = version_id
        self._maybe_fail("retire_active")

    async def publish_version(self, snapshot: CatalogueSnapshot) -> None:
        self.ops.append("publish_version")
        self._staged_publish = snapshot.version_id
        self._maybe_fail("publish_version")

    async def write_audit(self, *, version_id, action, actor_id, payload) -> None:
        self.ops.append("write_audit")
        self._staged_audit = {
            "version_id": version_id, "action": action,
            "actor_id": actor_id, "payload": payload,
        }
        self._maybe_fail("write_audit")

    async def write_sync_receipt(self, receipt: SyncReceipt) -> None:
        self.ops.append("write_sync_receipt")
        self._staged_receipt = receipt
        self._maybe_fail("write_sync_receipt")

    # The transaction fence: apply every staged mutation iff the whole call succeeded.
    def commit(self) -> None:
        if self._staged_records is not None:
            self._store.records[self._staged_records[0]] = self._staged_records[1]
        if self._staged_retire is not None:
            self._store.retired.append(self._staged_retire)
        if self._staged_publish is not None:
            self._store.active = self._staged_publish
        if self._staged_audit is not None:
            self._store.audit.append(self._staged_audit)
        if self._staged_receipt is not None:
            self._store.receipts.append(self._staged_receipt)


class ActivationStore:
    """Shared committed state across sequential activations (the serving cache + pointer)."""

    def __init__(self) -> None:
        self.active: UUID | None = None
        self.retired: list[UUID] = []
        self.records: dict[UUID, int] = {}
        self.audit: list[dict[str, object]] = []
        self.receipts: list[SyncReceipt] = []
        self.locked = False


async def _run(store: ActivationStore, snapshot: CatalogueSnapshot, expected: UUID | None,
               *, fail_on: str | None = None) -> SyncReceipt:
    port = FakeActivationPort(store, fail_on=fail_on)
    try:
        receipt = await activate_version(port, snapshot, expected, actor_id=_ACTOR)
    except BaseException:
        # Exception rolls back: no staged mutation is applied. Mirrors request_scope semantics.
        raise
    else:
        port.commit()
        return receipt


# --- ActivationPort protocol parity ---------------------------------------------------------

def test_fake_port_satisfies_activation_protocol() -> None:
    assert isinstance(FakeActivationPort(ActivationStore()), ActivationPort)


# --- happy path: validate -> copy -> flip, atomically and in order --------------------------

async def test_activation_validates_copies_then_flips_in_order() -> None:
    store = ActivationStore()
    snapshot = _valid_snapshot()

    receipt = await _run(store, snapshot, expected=None)

    assert receipt.state == "activated"
    assert receipt.version_id == _VERSION_A
    assert receipt.record_count == len(snapshot.records)
    assert receipt.content_sha256 == snapshot.content_sha256
    assert store.active == _VERSION_A
    assert store.records[_VERSION_A] == len(snapshot.records)
    assert len(store.audit) == 1
    assert len(store.receipts) == 1


async def test_activation_order_lock_then_compare_then_copy_then_flip_then_audit() -> None:
    store = ActivationStore()
    port = FakeActivationPort(store)
    await activate_version(port, _valid_snapshot(), None, actor_id=_ACTOR)
    # Lock is taken before the pointer is read; the pointer is flipped only after records are
    # copied; audit + receipt are written last, all inside the same transaction.
    assert port.ops == [
        "acquire_lock",
        "current_active_version",
        "upsert_records",
        "publish_version",
        "write_audit",
        "write_sync_receipt",
    ]


async def test_second_activation_retires_previous_and_keeps_one_active() -> None:
    store = ActivationStore()
    await _run(store, _valid_snapshot(_VERSION_A), expected=None)
    await _run(store, _valid_snapshot(_VERSION_B), expected=_VERSION_A)

    assert store.active == _VERSION_B
    assert store.retired == [_VERSION_A]
    # Historical records for the superseded version are NOT deleted from the serving cache.
    assert set(store.records) == {_VERSION_A, _VERSION_B}


# --- compare-and-set: a stale expected pointer is a CONFLICT, one version stays active -------

async def test_stale_expected_pointer_is_rejected_as_conflict() -> None:
    store = ActivationStore()
    await _run(store, _valid_snapshot(_VERSION_A), expected=None)

    # A second publisher believes nothing is active yet (stale) and tries to publish B.
    with pytest.raises(ActivationConflict) as excinfo:
        await _run(store, _valid_snapshot(_VERSION_B), expected=None)

    assert excinfo.value.code == "CONFLICT"
    assert excinfo.value.http_status == 409
    # Exactly one active version remains, and it is the first one; B never published.
    assert store.active == _VERSION_A
    assert store.retired == []
    assert _VERSION_B not in store.records
    assert len(store.receipts) == 1


async def test_two_concurrent_publishers_leave_exactly_one_active() -> None:
    store = ActivationStore()
    # Both publishers observed an empty pointer. The first to run wins; the second is stale.
    await _run(store, _valid_snapshot(_VERSION_A), expected=None)
    with pytest.raises(ActivationConflict):
        await _run(store, _valid_snapshot(_VERSION_B), expected=None)
    assert store.active == _VERSION_A
    assert sum(1 for v in (store.active,) if v is not None) == 1


# --- invalid snapshot never activates -------------------------------------------------------

async def test_invalid_snapshot_never_activates() -> None:
    store = ActivationStore()
    with pytest.raises(SnapshotInvalid) as excinfo:
        await _run(store, _invalid_snapshot(), expected=None)

    assert excinfo.value.code == "VALIDATION_FAILED"
    assert excinfo.value.http_status == 422
    assert store.active is None
    assert store.records == {}
    assert store.audit == []
    assert store.receipts == []


async def test_tampered_digest_snapshot_is_rejected_before_activation() -> None:
    store = ActivationStore()
    good = _valid_snapshot()
    tampered = CatalogueSnapshot(
        version_id=good.version_id, source=good.source,
        content_sha256="0" * 64, records=good.records,
    )
    with pytest.raises(SnapshotInvalid):
        await _run(store, tampered, expected=None)
    assert store.active is None
    assert store.records == {}


# --- audit + receipt are written in the SAME transaction (rollback assertion) ---------------

@pytest.mark.parametrize("fail_on", ["upsert_records", "publish_version", "write_audit",
                                     "write_sync_receipt"])
async def test_failure_rolls_back_pointer_records_and_audit_together(fail_on: str) -> None:
    store = ActivationStore()
    with pytest.raises(RuntimeError):
        await _run(store, _valid_snapshot(), expected=None, fail_on=fail_on)
    # Whatever step failed, nothing is committed: no active pointer, no records, no audit row,
    # no receipt. The remote version stays unactivated and safe to reconcile.
    assert store.active is None
    assert store.records == {}
    assert store.audit == []
    assert store.receipts == []


async def test_audit_and_receipt_accompany_a_successful_activation() -> None:
    store = ActivationStore()
    receipt = await _run(store, _valid_snapshot(), expected=None)
    assert len(store.audit) == 1
    entry = store.audit[0]
    assert entry["action"] == "catalogue.activated"
    assert entry["actor_id"] == _ACTOR
    assert entry["version_id"] == _VERSION_A
    assert store.receipts == [receipt]


async def test_failure_after_first_activation_keeps_first_version_active() -> None:
    store = ActivationStore()
    await _run(store, _valid_snapshot(_VERSION_A), expected=None)
    with pytest.raises(RuntimeError):
        await _run(store, _valid_snapshot(_VERSION_B), expected=_VERSION_A, fail_on="write_audit")
    # The in-flight activation of B rolled back entirely; A is still the single active version.
    assert store.active == _VERSION_A
    assert store.retired == []
    assert _VERSION_B not in store.records


def test_activation_errors_are_partsiq_errors() -> None:
    assert issubclass(ActivationConflict, PartsIQError)
    assert issubclass(SnapshotInvalid, PartsIQError)


# --- migration files exist and contain the real objects -------------------------------------

def test_all_five_build_kit_migrations_exist() -> None:
    for name in _TARGET_MIGRATIONS:
        path = _MIGRATIONS / name
        assert path.is_file(), f"missing migration {name}"
        assert path.read_text(encoding="utf-8").strip(), f"empty migration {name}"


def test_legacy_timestamped_migrations_coexist_untouched() -> None:
    # The earlier multi-service build shipped timestamped migrations; prompt 03 ADDS the 001-005
    # files ALONGSIDE them rather than replacing them (known reconciliation item).
    legacy = sorted(p.name for p in _MIGRATIONS.glob("20261011*.sql"))
    assert legacy, "legacy timestamped migrations must remain present"


def test_initial_schema_has_append_only_audit_and_cycle_guard() -> None:
    sql = _read("001_initial_schema.sql")
    assert "CREATE TABLE audit_log" in sql
    assert "audit_log is append-only" in sql
    assert "CREATE TRIGGER audit_log_no_update_delete" in sql
    # Supersession cycle protection and serial-range overlap exclusion are real constraints.
    assert "prevent_supersession_cycle" in sql
    assert "EXCLUDE USING gist" in sql
    # The candidate table carries the enquiry/rank key before the per-item revision keys land.
    assert "CREATE TABLE enquiry_candidates" in sql


def test_search_migration_adds_canonical_part_number_key() -> None:
    sql = _read("002_search_and_fulfilment.sql")
    assert "part_number_key" in sql
    assert "warehouse_transfer_routes" in sql


def test_application_migration_has_single_active_backstop_and_candidate_revision_keys() -> None:
    sql = _read("003_application.sql")
    # Serving cache + versions.
    assert "CREATE TABLE catalogue_versions" in sql
    assert "CREATE TABLE catalogue_records" in sql
    # The single-active-version backstop: a partial unique index on the published state.
    assert "catalogue_one_published_idx" in sql
    assert "WHERE state='published'" in sql
    # The per-item candidate/revision keys replace the legacy enquiry/rank primary key.
    assert "ALTER TABLE enquiry_candidates ADD PRIMARY KEY(item_id,revision,rank)" in sql
    assert "ALTER TABLE enquiry_candidates ADD UNIQUE(item_id,revision,part_id)" in sql
    # The serving-cache rows are immutable historical records.
    assert "catalogue_records_immutable" in sql
    assert "revisions_immutable" in sql
    # One published recommendation message per enquiry revision.
    assert "messages_one_publication_idx" in sql


def test_rls_migration_enables_rls_and_defines_nologin_group_roles() -> None:
    sql = _read("004_rls.sql")
    # NOLOGIN runtime group roles, one per service surface.
    for role in ("partsiq_api", "partsiq_search", "partsiq_workflow",
                 "partsiq_worker", "partsiq_catalogue"):
        assert f"CREATE ROLE {role} NOLOGIN" in sql
    # RLS is enabled on the operational and serving tables, and anon/authenticated are revoked.
    assert "ALTER TABLE enquiries ENABLE ROW LEVEL SECURITY" in sql
    assert "ALTER TABLE catalogue_records ENABLE ROW LEVEL SECURITY" in sql
    assert "ALTER TABLE catalogue_versions ENABLE ROW LEVEL SECURITY" in sql
    assert "REVOKE ALL ON enquiries FROM anon,authenticated" in sql
    # Only the publisher role may write serving rows; others are read-only.
    assert "GRANT SELECT,INSERT,UPDATE ON catalogue_records TO partsiq_catalogue" in sql
    assert "GRANT SELECT ON catalogue_records TO partsiq_api" in sql
    # The audit trail is append-only at the grant level too (INSERT only for writers).
    assert "GRANT INSERT ON audit_log TO partsiq_api" in sql


def test_storage_migration_creates_private_buckets_and_scoped_policies() -> None:
    sql = _read("005_storage.sql")
    for bucket in ("nameplates", "catalogue-evidence", "imports", "exports"):
        assert bucket in sql
    assert "partsiq_storage_allowed" in sql
    assert "CREATE POLICY nameplate_insert ON storage.objects" in sql


def test_config_toml_is_local_only() -> None:
    config = (_REPO_ROOT / "supabase" / "config.toml").read_text(encoding="utf-8")
    assert 'project_id = "partsiq"' in config
    assert "LOCAL development only" in config


# --- a live-database round-trip is BLOCKED here and is skipped, never faked ------------------

@pytest.mark.skip(reason="BLOCKED: live Postgres/Supabase unavailable in this environment")
async def test_live_activation_roundtrip_blocked() -> None:  # pragma: no cover
    # Would apply migrations 001-005 to a disposable local Postgres, bind the publisher role,
    # activate a validated snapshot through the asyncpg ActivationPort, and assert exactly one
    # published catalogue_versions row plus one audit_log + catalogue_syncs row. Requires a live
    # database, which is not available here; it must never be replaced with a fake.
    raise AssertionError("must run against a disposable local database")


def test_activation_module_imports_without_database() -> None:
    assert hasattr(activation_mod, "activate_version")
    assert uuid4()  # sanity: uuid import is used by the fixtures above
