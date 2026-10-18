"""End-to-end API integration (fixture mode) against the wired single FastAPI app.

Proves the consolidated ``apps/api/partsiq`` backend actually serves the customer + demo
journey over ``/v1`` with NO database — the in-memory fixture container + seed-42 catalogue
stand in. TestClient is used as a context manager so the lifespan runs (it wires the fixture
actor verifier onto ``app.state``). Everything here is synthetic demo data.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from partsiq.core.settings import Settings
from partsiq.main import create_app

DEMO = {"X-Demo-Token": "demo-integration"}


@pytest.fixture()
def client():
    with TestClient(create_app(Settings(app_env="test", data_source="fixture"))) as c:
        yield c


def _mutate_headers() -> dict[str, str]:
    return {**DEMO, "Idempotency-Key": str(uuid4())}


def test_health_is_credit_free(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_demo_access_requires_a_demo_token(client: TestClient) -> None:
    # No X-Demo-Token -> the fixture verifier refuses rather than trust an unverified identity.
    assert client.get("/v1/demo/scenarios").status_code == 401


def test_demo_scenarios_returns_four_seed42_scenarios(client: TestClient) -> None:
    resp = client.get("/v1/demo/scenarios", headers=DEMO)
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()["items"]]
    assert ids == ["mixed_photo", "missing_serial", "incompatible_number", "local_shortage"]


def test_demo_session_create_and_reset(client: TestClient) -> None:
    created = client.post(
        "/v1/demo/sessions", headers=_mutate_headers(), json={"expected_revision": 1}
    )
    assert created.status_code == 201
    session_id = created.json()["id"]
    gen1 = created.json()["generation"]
    reset = client.post(
        f"/v1/demo/sessions/{session_id}/reset",
        headers=_mutate_headers(),
        json={"expected_revision": 1},
    )
    assert reset.status_code == 201
    assert reset.json()["generation"] > gen1  # reset bumps the generation for isolation


def test_customer_enquiry_journey_in_fixture_mode(client: TestClient) -> None:
    headers = _mutate_headers()
    created = client.post(
        "/v1/enquiries",
        headers=headers,
        json={"text": "need oil filter for CAT 320", "locale": "en", "destination_warehouse_id": 1},
    )
    assert created.status_code == 202
    enquiry_id = created.json()["id"]

    assert client.get(f"/v1/enquiries/{enquiry_id}", headers=DEMO).status_code == 200
    assert client.get(f"/v1/enquiries/{enquiry_id}/progress", headers=DEMO).status_code == 200
    assert client.get(f"/v1/enquiries/{enquiry_id}/extraction", headers=DEMO).status_code == 200
    assert client.get(f"/v1/enquiries/{enquiry_id}/messages", headers=DEMO).status_code == 200


def test_mutation_requires_idempotency_key(client: TestClient) -> None:
    resp = client.post(
        "/v1/enquiries",
        headers=DEMO,  # no Idempotency-Key
        json={"text": "x", "locale": "en", "destination_warehouse_id": 1},
    )
    assert resp.status_code == 400


def test_idempotent_replay_returns_same_enquiry(client: TestClient) -> None:
    headers = _mutate_headers()
    payload = {"text": "need filter", "locale": "en", "destination_warehouse_id": 1}
    first = client.post("/v1/enquiries", headers=headers, json=payload)
    second = client.post("/v1/enquiries", headers=headers, json=payload)
    assert first.status_code == 202 and second.status_code == 202
    assert first.json()["id"] == second.json()["id"]


def test_foreign_actor_cannot_read_anothers_enquiry(client: TestClient) -> None:
    created = client.post("/v1/enquiries", headers=_mutate_headers(),
                          json={"text": "mine", "locale": "en", "destination_warehouse_id": 1})
    enquiry_id = created.json()["id"]
    foreign = client.get(f"/v1/enquiries/{enquiry_id}", headers={"X-Demo-Token": "someone-else"})
    assert foreign.status_code == 404  # ownership isolation, not a 403 that leaks existence


def test_every_registered_v1_route_is_mounted(client: TestClient) -> None:
    app = client.app
    paths = {r.path for r in app.routes if getattr(r, "path", "").startswith("/v1")}
    for expected in (
        "/v1/demo/scenarios",
        "/v1/enquiries",
        "/v1/enquiries/{enquiry_id}",
        "/v1/enquiries/{enquiry_id}/progress",
    ):
        assert expected in paths
