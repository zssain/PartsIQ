"""Foundation 02 acceptance: Snowflake connector + validated catalogue source.

Every test here is OFFLINE and deterministic. The Snowflake repository is exercised through a
fake connection/cursor (the injected :class:`SnowflakeConnection` protocol); the fixture
repository uses in-memory and on-disk JSON. Live Snowflake behaviour is BLOCKED in this
environment (the connector is not installed and no warehouse allowance is confirmed) and is
marked SKIP rather than faked — see ``test_live_snowflake_blocked``.
"""
from __future__ import annotations

import importlib
import json
import re
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from partsiq.catalogue import fixture_repository as fixture_mod
from partsiq.catalogue import models as catalogue_models
from partsiq.catalogue import snowflake_repository as sf_mod
from partsiq.catalogue.fixture_repository import FixtureCatalogueRepository
from partsiq.catalogue.models import (
    CATALOGUE_ENTITY_TYPES,
    CatalogueSource,
    build_snapshot,
    content_sha256,
    row_sha256,
)
from partsiq.catalogue.snowflake_repository import (
    SnowflakeCatalogueRepository,
    open_connection,
)
from partsiq.catalogue.validation import validate_snapshot
from partsiq.core.api_models import (
    CatalogueRecord,
    CatalogueSnapshot,
    SyncReceipt,
    ValidationIssue,
)
from partsiq.core.errors import PartsIQError
from partsiq.core.settings import Settings

_SHA_RE = re.compile(r"^[a-f0-9]{64}$")
_VERSION = UUID("11111111-1111-1111-1111-111111111111")
_REPO_ROOT = Path(__file__).resolve().parents[3]
_INFRA_SNOWFLAKE = _REPO_ROOT / "infra" / "snowflake"


# --- synthetic, VALID catalogue -----------------------------------------

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
        CatalogueRecord(entity_type="model_configurations", entity_key='["ACME","X9","B"]',
                        payload={"brand": "ACME", "model_code": "X9", "config_code": "B",
                                 "serial_start": 101, "serial_end": 200}),
        CatalogueRecord(entity_type="parts", entity_key="101",
                        payload={"part_number": "FLT-101", "name_en": "Oil filter", "name_ar": "فلتر زيت",
                                 "category": "filters", "unit_of_measure": "ea", "is_active": True}),
        CatalogueRecord(entity_type="parts", entity_key="102",
                        payload={"part_number": "FLT-102", "name_en": "Air filter", "name_ar": "فلتر هواء",
                                 "category": "filters", "unit_of_measure": "ea", "is_active": True}),
        CatalogueRecord(entity_type="part_compatibility", entity_key='["101","ACME","X9","A"]',
                        payload={"part_number": "FLT-101", "brand": "ACME", "model_code": "X9",
                                 "config_code": "A", "quantity_per_unit": 1, "source_reference": "Manual p.12"}),
        CatalogueRecord(entity_type="part_supersessions", entity_key='["FLT-101","FLT-102"]',
                        payload={"old_part_number": "FLT-101", "new_part_number": "FLT-102",
                                 "effective_date": "2026-01-01"}),
    ]


def _valid_snapshot() -> CatalogueSnapshot:
    return build_snapshot(version_id=_VERSION, source="fixture", records=_valid_records())


# --- canonical hashing ---------------------------------------------------

def test_content_sha256_is_order_independent() -> None:
    records = _valid_records()
    forward = content_sha256(records)
    backward = content_sha256(list(reversed(records)))
    assert forward == backward
    assert _SHA_RE.match(forward)


def test_content_sha256_changes_with_content() -> None:
    base = _valid_records()
    mutated = list(base)
    mutated[4] = CatalogueRecord(
        entity_type="parts", entity_key="101",
        payload={**base[4].payload, "name_en": "Different"},
    )
    assert content_sha256(base) != content_sha256(mutated)


def test_numeric_ids_preserved_not_uuid() -> None:
    snap = _valid_snapshot()
    part = next(r for r in snap.records if r.entity_type == "parts")
    assert part.entity_key == "101"  # decimal-string numeric id, never a UUID
    assert row_sha256(part) == row_sha256(part)


# --- validation ----------------------------------------------------------

def test_valid_snapshot_has_no_issues() -> None:
    assert validate_snapshot(_valid_snapshot()) == []


def _codes(issues: list[ValidationIssue]) -> set[str]:
    return {issue.code for issue in issues}


def test_validation_rejects_unknown_entity_type() -> None:
    snap = build_snapshot(version_id=_VERSION, source="fixture", records=[
        CatalogueRecord(entity_type="not_a_real_entity", entity_key="1", payload={}),
    ])
    assert "UNKNOWN_ENTITY_TYPE" in _codes(validate_snapshot(snap))


def test_validation_rejects_missing_required_field() -> None:
    snap = build_snapshot(version_id=_VERSION, source="fixture", records=[
        CatalogueRecord(entity_type="parts", entity_key="1",
                        payload={"part_number": "P1"}),  # missing name_en/name_ar/...
    ])
    assert "MISSING_FIELD" in _codes(validate_snapshot(snap))


def test_validation_quarantines_duplicate_keys_not_overwrite() -> None:
    records = _valid_records()
    records.append(records[4])  # a second parts row with key "101"
    snap = build_snapshot(version_id=_VERSION, source="fixture", records=records)
    issues = validate_snapshot(snap)
    assert "DUPLICATE_KEY" in _codes(issues)


def test_validation_detects_serial_overlap() -> None:
    records = _valid_records()
    records[3] = CatalogueRecord(  # make config B overlap config A
        entity_type="model_configurations", entity_key='["ACME","X9","B"]',
        payload={"brand": "ACME", "model_code": "X9", "config_code": "B",
                 "serial_start": 50, "serial_end": 150},
    )
    assert "SERIAL_RANGE_OVERLAP" in _codes(validate_snapshot(
        build_snapshot(version_id=_VERSION, source="fixture", records=records)))


def test_validation_detects_supersession_cycle() -> None:
    records = _valid_records()
    records[-1] = CatalogueRecord(entity_type="part_supersessions", entity_key='["FLT-101","FLT-102"]',
                                  payload={"old_part_number": "FLT-101", "new_part_number": "FLT-102",
                                           "effective_date": "2026-01-01"})
    records.append(CatalogueRecord(entity_type="part_supersessions", entity_key='["FLT-102","FLT-101"]',
                                   payload={"old_part_number": "FLT-102", "new_part_number": "FLT-101",
                                            "effective_date": "2026-02-01"}))
    assert "SUPERSESSION_CYCLE" in _codes(validate_snapshot(
        build_snapshot(version_id=_VERSION, source="fixture", records=records)))


def test_validation_detects_self_supersession() -> None:
    records = _valid_records()
    records[-1] = CatalogueRecord(entity_type="part_supersessions", entity_key='["FLT-101","FLT-101"]',
                                  payload={"old_part_number": "FLT-101", "new_part_number": "FLT-101",
                                           "effective_date": "2026-01-01"})
    assert "SUPERSESSION_SELF_LOOP" in _codes(validate_snapshot(
        build_snapshot(version_id=_VERSION, source="fixture", records=records)))


def test_validation_requires_source_evidence() -> None:
    records = _valid_records()
    records[6] = CatalogueRecord(entity_type="part_compatibility", entity_key='["101","ACME","X9","A"]',
                                 payload={"part_number": "FLT-101", "brand": "ACME", "model_code": "X9",
                                          "config_code": "A", "quantity_per_unit": 1, "source_reference": "  "})
    assert "MISSING_EVIDENCE" in _codes(validate_snapshot(
        build_snapshot(version_id=_VERSION, source="fixture", records=records)))


def test_validation_rejects_unknown_reference_and_bad_quantity() -> None:
    records = _valid_records()
    records[6] = CatalogueRecord(entity_type="part_compatibility", entity_key='["999","ACME","X9","A"]',
                                 payload={"part_number": "GHOST", "brand": "ACME", "model_code": "X9",
                                          "config_code": "A", "quantity_per_unit": 0,
                                          "source_reference": "ref"})
    codes = _codes(validate_snapshot(build_snapshot(version_id=_VERSION, source="fixture", records=records)))
    assert "UNKNOWN_REFERENCE" in codes
    assert "INVALID_QUANTITY" in codes


# --- fixture repository --------------------------------------------------

def test_fixture_repository_roundtrip_and_source_label() -> None:
    repo = FixtureCatalogueRepository.from_versions({_VERSION: _valid_records()})
    assert isinstance(repo, CatalogueSource)  # satisfies the common interface
    snap = repo.read_version(_VERSION)
    assert snap.source == "fixture"
    assert snap.version_id == _VERSION
    assert snap.content_sha256 == content_sha256(_valid_records())
    assert validate_snapshot(snap) == []


def test_fixture_repository_unknown_version_is_not_found() -> None:
    repo = FixtureCatalogueRepository.from_versions({_VERSION: _valid_records()})
    with pytest.raises(PartsIQError) as excinfo:
        repo.read_version(uuid4())
    assert excinfo.value.code == "NOT_FOUND"


def test_fixture_repository_from_file(tmp_path: Path) -> None:
    document = {"versions": {str(_VERSION): [
        {"entity_type": r.entity_type, "entity_key": r.entity_key, "payload": r.payload}
        for r in _valid_records()
    ]}}
    path = tmp_path / "catalogue.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    repo = FixtureCatalogueRepository.from_file(path)
    snap = repo.read_version(_VERSION)
    assert snap.source == "fixture" and len(snap.records) == len(_valid_records())


def test_fixture_repository_missing_file_is_dependency_error(tmp_path: Path) -> None:
    with pytest.raises(PartsIQError) as excinfo:
        FixtureCatalogueRepository.from_file(tmp_path / "nope.json")
    assert excinfo.value.code == "DEPENDENCY_UNAVAILABLE"


# --- fake Snowflake cursor/connection ------------------------------------

class _FakeCursor:
    def __init__(self, conn: "_FakeConnection") -> None:
        self._conn = conn
        self.sfqid = "01ab-fake-query-id"
        self._result: list[tuple] = []

    def execute(self, command: str, params: object | None = None) -> object:
        self._conn.statements.append((command, params))
        upper = command.strip().upper()
        if upper == "BEGIN":
            self._result = []
        elif "FROM" in upper and ".VERSIONS" in upper and "SELECT" in upper:
            self._result = list(self._conn.version_rows)
        elif "FROM" in upper and ".RECORDS" in upper and "SELECT" in upper:
            self._result = list(self._conn.record_rows)
        elif upper.startswith("INSERT"):
            self._conn.inserts.append((command, params))
            self._result = []
        else:
            self._result = []
        return self

    def fetchall(self) -> list[tuple]:
        return self._result

    def close(self) -> None:
        self._conn.closed_cursors += 1


class _FakeConnection:
    def __init__(self, *, version_rows: list[tuple], record_rows: list[tuple],
                 raise_on: str | None = None) -> None:
        self.version_rows = version_rows
        self.record_rows = record_rows
        self.statements: list[tuple] = []
        self.inserts: list[tuple] = []
        self.committed = 0
        self.rolled_back = 0
        self.closed_cursors = 0
        self._raise_on = raise_on

    def cursor(self) -> _FakeCursor:
        cursor = _FakeCursor(self)
        if self._raise_on is not None:
            original = cursor.execute

            def guarded(command: str, params: object | None = None):  # type: ignore[no-untyped-def]
                if self._raise_on in command:
                    raise RuntimeError("simulated snowflake failure")
                return original(command, params)

            cursor.execute = guarded  # type: ignore[method-assign]
        return cursor

    def commit(self) -> None:
        self.committed += 1

    def rollback(self) -> None:
        self.rolled_back += 1

    def close(self) -> None:  # pragma: no cover - not exercised
        pass


def _remote_rows(records: list[CatalogueRecord]):
    ordered = sorted(records, key=lambda r: (r.entity_type, r.entity_key))
    rows = [(r.entity_type, r.entity_key, json.dumps(r.payload), row_sha256(r)) for r in ordered]
    return rows


def _settings() -> Settings:
    return Settings(app_env="test", data_source="snowflake", snowflake_database="PARTSIQ_DEV")


# --- Snowflake repository (read) -----------------------------------------

def test_snowflake_read_version_roundtrip_with_verified_digest() -> None:
    records = _valid_records()
    sha = content_sha256(records)
    conn = _FakeConnection(
        version_rows=[(str(_VERSION), sha, len(records), "2026-01-01T00:00:00Z")],
        record_rows=_remote_rows(records),
    )
    repo = SnowflakeCatalogueRepository(conn, _settings())
    assert isinstance(repo, CatalogueSource)
    snap = repo.read_version(_VERSION)
    assert snap.source == "snowflake"
    assert snap.content_sha256 == sha
    assert len(snap.records) == len(records)
    assert conn.closed_cursors >= 1  # cursor closed in finally
    # fixed SQL used bound parameters, never string-formatted values
    read_sql = [s for s, _ in conn.statements if "RECORDS" in s][0]
    assert "?" in read_sql and str(_VERSION) not in read_sql


def test_snowflake_read_version_fixed_identifier_in_sql() -> None:
    records = _valid_records()
    conn = _FakeConnection(
        version_rows=[(str(_VERSION), content_sha256(records), len(records), "t")],
        record_rows=_remote_rows(records),
    )
    SnowflakeCatalogueRepository(conn, _settings()).read_version(_VERSION)
    assert all("PARTSIQ_DEV.CATALOGUE" in s for s, _ in conn.statements if "FROM" in s)


def test_snowflake_read_rejects_count_mismatch() -> None:
    records = _valid_records()
    conn = _FakeConnection(
        version_rows=[(str(_VERSION), content_sha256(records), len(records) + 1, "t")],
        record_rows=_remote_rows(records),
    )
    with pytest.raises(PartsIQError) as excinfo:
        SnowflakeCatalogueRepository(conn, _settings()).read_version(_VERSION)
    assert excinfo.value.code == "STALE_CATALOGUE"


def test_snowflake_read_rejects_digest_mismatch() -> None:
    records = _valid_records()
    conn = _FakeConnection(
        version_rows=[(str(_VERSION), "0" * 64, len(records), "t")],
        record_rows=_remote_rows(records),
    )
    with pytest.raises(PartsIQError) as excinfo:
        SnowflakeCatalogueRepository(conn, _settings()).read_version(_VERSION)
    assert excinfo.value.code == "STALE_CATALOGUE"


def test_snowflake_read_unknown_version_is_not_found() -> None:
    conn = _FakeConnection(version_rows=[], record_rows=[])
    with pytest.raises(PartsIQError) as excinfo:
        SnowflakeCatalogueRepository(conn, _settings()).read_version(_VERSION)
    assert excinfo.value.code == "NOT_FOUND"


def test_snowflake_read_failure_maps_to_dependency_error_no_fallback() -> None:
    # A Snowflake exception must map to a stable code, never silently switch to fixtures.
    conn = _FakeConnection(version_rows=[], record_rows=[], raise_on="VERSIONS")
    with pytest.raises(PartsIQError) as excinfo:
        SnowflakeCatalogueRepository(conn, _settings()).read_version(_VERSION)
    assert excinfo.value.code == "DEPENDENCY_UNAVAILABLE"
    assert conn.closed_cursors >= 1


# --- Snowflake repository (write) ----------------------------------------

def test_snowflake_write_version_commits_and_records_query_id() -> None:
    snap = _valid_snapshot()
    conn = _FakeConnection(version_rows=[], record_rows=[])
    receipt = SnowflakeCatalogueRepository(conn, _settings()).write_version(snap)
    assert isinstance(receipt, SyncReceipt)
    assert receipt.state == "remote_written"
    assert receipt.record_count == len(snap.records)
    assert receipt.query_id == "01ab-fake-query-id"  # sfqid stored
    assert conn.committed == 1 and conn.rolled_back == 0
    # one VERSIONS insert + one per record, all bound (no literal version id in the SQL text)
    assert len(conn.inserts) == 1 + len(snap.records)
    assert all("?" in sql for sql, _ in conn.inserts)


def test_snowflake_write_version_rolls_back_on_failure() -> None:
    snap = _valid_snapshot()
    conn = _FakeConnection(version_rows=[], record_rows=[], raise_on="INSERT INTO PARTSIQ_DEV.CATALOGUE.RECORDS")
    receipt = SnowflakeCatalogueRepository(conn, _settings()).write_version(snap)
    assert receipt.state == "failed"
    assert conn.rolled_back == 1 and conn.committed == 0


# --- module import / live Snowflake BLOCKED ------------------------------

def test_module_imports_without_connector_installed() -> None:
    # The connector is not installed; importing the repository module must still succeed.
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("snowflake.connector")
    reloaded = importlib.reload(sf_mod)
    assert hasattr(reloaded, "SnowflakeCatalogueRepository")


def test_open_connection_blocked_without_connector() -> None:
    # Live Snowflake is BLOCKED here: open_connection must raise a clear dependency error
    # rather than fabricate a connection.
    with pytest.raises(PartsIQError) as excinfo:
        open_connection(_settings())
    assert excinfo.value.code == "DEPENDENCY_UNAVAILABLE"


@pytest.mark.skip(reason="BLOCKED: live Snowflake unavailable (connector not installed, no confirmed warehouse allowance)")
def test_live_snowflake_roundtrip() -> None:  # pragma: no cover - never runs offline
    raise AssertionError("must not run without a confirmed live Snowflake allowance")


# --- infra SQL assertions (schema/roles/validation are setup-only) -------

def test_infra_snowflake_schema_sql_present_and_shaped() -> None:
    schema_sql = (_INFRA_SNOWFLAKE / "001_schema.sql").read_text(encoding="utf-8")
    assert "PARTSIQ_DEV.CATALOGUE.VERSIONS" in schema_sql
    assert "PARTSIQ_DEV.CATALOGUE.RECORDS" in schema_sql
    assert "PARTSIQ_DEV.CATALOGUE.STOCK_SNAPSHOTS" in schema_sql
    assert "PARTSIQ_DEV.REPORTING.EVENTS" in schema_sql
    assert "CONTENT_SHA256" in schema_sql and "ROW_SHA256" in schema_sql


def test_infra_snowflake_roles_least_privilege() -> None:
    roles_sql = (_INFRA_SNOWFLAKE / "002_roles.sql").read_text(encoding="utf-8")
    for role in ("PARTSIQ_READER", "PARTSIQ_LOADER", "PARTSIQ_REPORTER"):
        assert role in roles_sql
    assert "ACCOUNTADMIN" not in roles_sql and "SECURITYADMIN" not in roles_sql


def test_infra_snowflake_validation_queries_present() -> None:
    validation_sql = (_INFRA_SNOWFLAKE / "003_validation_queries.sql").read_text(encoding="utf-8")
    assert "HAVING COUNT(*)<>1" in validation_sql  # duplicate-key diagnostic
    assert "RESERVED>ON_HAND" in validation_sql  # stock value diagnostic


# --- consistency sanity --------------------------------------------------

def test_entity_type_allowlist_matches_validation_required_fields() -> None:
    from partsiq.catalogue.validation import _REQUIRED_FIELDS

    assert set(_REQUIRED_FIELDS) == set(CATALOGUE_ENTITY_TYPES)


def test_models_and_fixture_share_source_literal() -> None:
    assert catalogue_models.CatalogueSourceName.__args__ == ("snowflake", "fixture")  # type: ignore[attr-defined]
    assert fixture_mod.FixtureCatalogueRepository.source == "fixture"
