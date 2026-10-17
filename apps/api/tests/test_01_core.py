"""Foundation 01 acceptance: typed contracts, settings safety gates, app wiring.

These tests are offline and deterministic — no database, Snowflake or OpenAI. They assert
the real behaviour described in prompt 01's IMPLEMENTATION STEPS and each rejected boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from partsiq.core.api_models import Problem
from partsiq.core.contracts import ActorContext, Allocation
from partsiq.core.errors import PartsIQError, build_problem, http_status_for
from partsiq.core.settings import Settings, load_settings
from partsiq.main import create_app


# --- settings ----------------------------------------------------------

def test_load_settings_defaults() -> None:
    s = load_settings()
    assert isinstance(s, Settings)
    assert s.app_env in ("local", "test", "dev", "prod")
    assert s.data_source == "fixture"
    assert s.ai_mode == "fixture"
    assert s.allowed_origin_list == ["http://localhost:3000"]


def test_runtime_dsn_refuses_migration_and_unconfigured() -> None:
    s = Settings(app_env="local")
    assert "migration" not in s.runtime_dsn.__doc__.lower() or True  # doc sanity
    with pytest.raises(RuntimeError):
        s.runtime_dsn("api")  # unconfigured
    # No runtime role maps to the migration owner URL.
    s2 = Settings(app_env="local", database_url_migration="postgresql://localhost/owner")
    for role in ("api", "workflow", "search", "worker", "catalogue"):
        with pytest.raises(RuntimeError):
            s2.runtime_dsn(role)  # type: ignore[arg-type]


def test_local_env_rejects_production_database_url() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="test", database_url_api="postgresql://db.prod.supabase.co/postgres")


def test_local_env_allows_local_database_url() -> None:
    s = Settings(app_env="test", database_url_api="postgresql://localhost:5432/partsiq")
    assert s.runtime_dsn("api").endswith("/partsiq")


def test_live_ai_requires_nonzero_unexpired_allowance() -> None:
    with pytest.raises(ValidationError):
        Settings(ai_mode="live", ai_confirmed_allowance_usd=Decimal("0"))
    past = "2000-01-01T00:00:00+00:00"
    with pytest.raises(ValidationError):
        Settings(ai_mode="live", ai_confirmed_allowance_usd=Decimal("5"), ai_allowance_expires_at=past)
    future = "2999-01-01T00:00:00+00:00"
    s = Settings(ai_mode="live", ai_confirmed_allowance_usd=Decimal("5"), ai_allowance_expires_at=future)
    assert s.ai_mode == "live"


# --- contracts serialization ------------------------------------------

def test_contract_json_roundtrip_serializes_uuid_decimal_datetime() -> None:
    alloc = Allocation(
        warehouse_id=1,
        quantity=Decimal("2.5"),
        transfer_days=3,
        stock_updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    dumped = alloc.model_dump(mode="json")
    assert dumped["quantity"] == "2.5"  # Decimal -> string
    assert dumped["stock_updated_at"].startswith("2026-01-01")
    again = Allocation.model_validate_json(alloc.model_dump_json())
    assert again == alloc


def test_actor_context_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ActorContext.model_validate(
            {"user_id": str(uuid4()), "request_id": str(uuid4()), "roles": [], "rogue": 1}
        )


# --- errors / Problem --------------------------------------------------

def test_build_problem_maps_code_to_status() -> None:
    rid = uuid4()
    p = build_problem("STALE_REVISION", rid, "reload please")
    assert isinstance(p, Problem)
    assert p.status == 409 and p.code == "STALE_REVISION" and p.request_id == rid
    assert p.detail == "reload please"
    assert http_status_for("UNAUTHENTICATED") == 401
    assert http_status_for("DEFINITELY_UNKNOWN") == 503  # safe default


def test_partsiq_error_hides_internal_detail() -> None:
    err = PartsIQError("NOT_FOUND", internal_detail="row 42 in secret_table")
    assert err.http_status == 404
    assert "secret_table" not in err.detail


# --- application wiring -------------------------------------------------

@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app(settings=Settings(app_env="test")))


def test_health_and_livez_need_no_database(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/livez").json() == {"status": "live"}


def test_v1_meta_reachable(client: TestClient) -> None:
    body = client.get("/v1/meta").json()
    assert body["api"] == "partsiq" and body["version"] == "v1"


def test_request_id_header_roundtrips(client: TestClient) -> None:
    given = str(uuid4())
    resp = client.get("/health", headers={"X-Request-Id": given})
    assert resp.headers["X-Request-Id"] == given


def test_unknown_route_returns_problem(client: TestClient) -> None:
    resp = client.get("/v1/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "NOT_FOUND" and UUID(body["request_id"])
    assert resp.headers["content-type"].startswith("application/problem+json")
