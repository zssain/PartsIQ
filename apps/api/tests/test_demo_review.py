"""Demo staff-review journey (F03 role switch + F04 own-session isolation) via canonical endpoints.

In the fixture demo the reviewer is the SAME anonymous session; the canonical /v1/staff review
endpoints are authorised by own-demo-session scope and served by the in-memory journey. Real
RBAC (DB mode) is unchanged. Everything is synthetic seed-42 data.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from partsiq.core.settings import Settings
from partsiq.main import create_app


@pytest.fixture()
def client():
    with TestClient(create_app(Settings(app_env="test", data_source="fixture"))) as c:
        yield c


def _create(client: TestClient, token: str) -> str:
    r = client.post(
        "/v1/enquiries",
        headers={"X-Demo-Token": token, "Idempotency-Key": str(uuid4())},
        json={"text": "Need 1 air filter element CA-AF-8973 for Corvane Air CA-110 serial 800123", "locale": "en", "destination_warehouse_id": 1},
    )
    assert r.status_code == 202
    return r.json()["id"]


def _draft(client: TestClient, token: str, enquiry_id: str) -> str:
    return client.get(f"/v1/staff/enquiries/{enquiry_id}", headers={"X-Demo-Token": token}).json()["draft_id"]


def _revision(client: TestClient, token: str, enquiry_id: str) -> int:
    return client.get(f"/v1/staff/enquiries/{enquiry_id}", headers={"X-Demo-Token": token}).json()[
        "enquiry"
    ]["revision"]


def test_workspace_assembles_real_seed42_review_content(client: TestClient) -> None:
    eid = _create(client, "rev")
    ws = client.get(f"/v1/staff/enquiries/{eid}", headers={"X-Demo-Token": "rev"}).json()
    item = ws["facts"]["items"][0]
    assert item["part_number"] == "CA-AF-8973" and item["name_en"] == "Air filter element"
    assert item["name_ar"]  # bilingual
    assert ws["verification"]["passed"] is True and ws["verification"]["failures"] == []
    # The draft prose carries NO digits/identifiers (code owns every fact).
    for slot in ("greeting", "explanation", "closing"):
        assert not any(ch.isdigit() for ch in ws["draft"][slot])


def test_approve_returns_approval_result_and_is_idempotent(client: TestClient) -> None:
    eid = _create(client, "rev")
    rev = _revision(client, "rev", eid)
    body = {"enquiry_id": eid, "expected_revision": rev, "draft_id": _draft(client, "rev", eid)}
    first = client.post(
        f"/v1/staff/enquiries/{eid}/approve",
        headers={"X-Demo-Token": "rev", "Idempotency-Key": str(uuid4())}, json=body,
    ).json()
    assert first["already_applied"] is False and first["decision_id"] and first["message_id"]
    second = client.post(
        f"/v1/staff/enquiries/{eid}/approve",
        headers={"X-Demo-Token": "rev", "Idempotency-Key": str(uuid4())}, json=body,
    ).json()
    assert second["already_applied"] is True and second["decision_id"] == first["decision_id"]
    enq = client.get(f"/v1/enquiries/{eid}", headers={"X-Demo-Token": "rev"}).json()
    assert enq["status"] == "approved"
    assert sum(1 for m in enq["messages"] if m["kind"] == "recommendation") == 1


def test_reject_records_reason_and_publishes_nothing(client: TestClient) -> None:
    eid = _create(client, "rev")
    rev = _revision(client, "rev", eid)
    res = client.post(
        f"/v1/staff/enquiries/{eid}/reject",
        headers={"X-Demo-Token": "rev", "Idempotency-Key": str(uuid4())},
        json={"enquiry_id": eid, "expected_revision": rev, "reason": "needs a clearer photo"},
    ).json()
    assert res["status"] == "rejected" and res["decision_id"]
    enq = client.get(f"/v1/enquiries/{eid}", headers={"X-Demo-Token": "rev"}).json()
    assert enq["status"] == "rejected"
    assert all(m["kind"] != "recommendation" for m in enq["messages"])  # never published


def test_inbox_is_own_session_only(client: TestClient) -> None:
    eid = _create(client, "owner")
    mine = client.get("/v1/staff/enquiries", headers={"X-Demo-Token": "owner"}).json()
    assert any(e["id"] == eid for e in mine["items"])  # owner sees their own enquiry
    other = client.get("/v1/staff/enquiries", headers={"X-Demo-Token": "stranger"}).json()
    assert all(e["id"] != eid for e in other["items"])  # a different session never sees it


def test_approval_with_a_different_draft_id_is_409(client: TestClient) -> None:
    eid = _create(client, "rev")
    res = client.post(
        f"/v1/staff/enquiries/{eid}/approve",
        headers={"X-Demo-Token": "rev", "Idempotency-Key": str(uuid4())},
        json={"enquiry_id": eid, "expected_revision": _revision(client, "rev", eid), "draft_id": str(uuid4())},
    )
    assert res.status_code == 409
    enq = client.get(f"/v1/enquiries/{eid}", headers={"X-Demo-Token": "rev"}).json()
    assert enq["status"] == "awaiting_review"  # nothing was published


def test_stale_revision_approval_is_409(client: TestClient) -> None:
    eid = _create(client, "rev")
    res = client.post(
        f"/v1/staff/enquiries/{eid}/approve",
        headers={"X-Demo-Token": "rev", "Idempotency-Key": str(uuid4())},
        json={"enquiry_id": eid, "expected_revision": 999, "draft_id": str(uuid4())},
    )
    assert res.status_code == 409
