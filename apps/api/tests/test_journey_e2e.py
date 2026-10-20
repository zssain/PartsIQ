"""End-to-end journey verification (fixture mode) through the LangGraph engine (Phase 6, backend).

Drives the complete loop over the wired `/v1` API with the in-memory fixture container:
create → real workflow run (LangGraph) → progress/timeline → human-review approval → published
reply. Then the resilience cases: refresh/resume, duplicate submission, duplicate/stale approval,
unauthorized access, and the fixture (no-credit) path.

Scope note (honest): per-scenario OUTCOME correctness (missing-serial → needs_information,
incompatible → needs_information, shortage → awaiting_review with a shortage) is asserted by the
deterministic evaluation suite `test_21_evaluation.py` against the seed-42 catalogue. This module
verifies that each of the four demo scenario inputs runs end-to-end through the persisted workflow
and that the loop/resilience guarantees hold. Browser (UI) checks are performed separately.
"""
from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from partsiq.core.settings import Settings
from partsiq.main import create_app

# apps/api/tests/test_journey_e2e.py -> repo root is parents[3].
_SCENARIOS = json.loads(
    (Path(__file__).resolve().parents[3] / "fixtures" / "scenarios.json").read_text()
)
_SCENARIO_LIST = _SCENARIOS["scenarios"] if isinstance(_SCENARIOS, dict) else _SCENARIOS
_SCENARIO_TEXTS = [s["text"] for s in _SCENARIO_LIST]


@pytest.fixture()
def client():
    with TestClient(create_app(Settings(app_env="test", data_source="fixture"))) as c:
        yield c


def _demo(token: str = "journey", key: bool = False) -> dict[str, str]:
    h = {"X-Demo-Token": token}
    if key:
        h["Idempotency-Key"] = str(uuid4())
    return h


def _create(client: TestClient, text: str, token: str = "journey") -> str:
    resp = client.post(
        "/v1/enquiries",
        headers=_demo(token, key=True),
        json={"text": text, "locale": "en", "destination_warehouse_id": 1},
    )
    assert resp.status_code == 202, resp.text
    return resp.json()["id"]


def _approve(client: TestClient, enquiry_id: str, token: str = "journey"):
    """Approve via the CANONICAL review endpoint (own-demo-session scope, F03 role switch)."""
    ws = client.get(f"/v1/staff/enquiries/{enquiry_id}", headers=_demo(token))
    body = ws.json() if ws.status_code == 200 else {}
    revision = body.get("enquiry", {}).get("revision", 1)
    # Approval binds to the exact server-side draft (a random id is a 409).
    draft_id = body.get("draft_id") or str(uuid4())
    return client.post(
        f"/v1/staff/enquiries/{enquiry_id}/approve",
        headers=_demo(token, key=True),
        json={"enquiry_id": enquiry_id, "expected_revision": revision, "draft_id": draft_id},
    )


# --- the happy-path loop ----------------------------------------------

def test_full_loop_create_progress_review_approve(client: TestClient) -> None:
    enquiry_id = _create(client, "Need 1 air filter element CA-AF-8973 for Corvane Air CA-110 serial 800123")
    # Progress reflects the real LangGraph run paused at human review.
    prog = client.get(f"/v1/enquiries/{enquiry_id}/progress", headers=_demo()).json()
    assert prog["step"] == "review"
    timeline = client.get(f"/v1/enquiries/{enquiry_id}/timeline", headers=_demo()).json()
    steps = [e["step"] for e in timeline["events"]]
    assert steps[:6] == ["intake", "identify", "search", "plan", "draft", "verify"]
    # Every event carries the concise evidence line recorded when the step actually ran.
    assert all(e.get("detail") for e in timeline["events"][:6])
    assert steps[-1] == "review"
    # The reviewer workspace assembles real seed-42 content (facts/draft/verification).
    ws = client.get(f"/v1/staff/enquiries/{enquiry_id}", headers=_demo()).json()
    assert ws["facts"]["items"][0]["part_number"] == "CA-AF-8973"
    assert ws["verification"]["passed"] is True
    # Human approval publishes exactly one recommendation reply (canonical review endpoint).
    result = _approve(client, enquiry_id).json()
    assert result["already_applied"] is False
    enq = client.get(f"/v1/enquiries/{enquiry_id}", headers=_demo()).json()
    assert enq["status"] == "approved"
    assert sum(1 for m in enq["messages"] if m["kind"] == "recommendation") == 1


# --- the four demo scenarios run end-to-end ---------------------------

def test_all_four_demo_scenarios_run_through_the_workflow(client: TestClient) -> None:
    assert len(_SCENARIO_TEXTS) == 4
    for i, text in enumerate(_SCENARIO_TEXTS):
        enquiry_id = _create(client, text, token=f"scenario-{i}")
        timeline = client.get(
            f"/v1/enquiries/{enquiry_id}/timeline", headers=_demo(f"scenario-{i}")
        ).json()
        # Each scenario persists and produces a real, ordered progress timeline (no fabricated
        # jump straight to a result; the workflow actually ran).
        assert timeline["events"][0]["step"] == "intake"
        assert len(timeline["events"]) >= 2


# --- resilience -------------------------------------------------------

def test_refresh_resume_is_consistent(client: TestClient) -> None:
    enquiry_id = _create(client, "Need 1 air filter element CA-AF-8973 for Corvane Air CA-110 serial 800123")
    first = client.get(f"/v1/enquiries/{enquiry_id}/timeline", headers=_demo()).json()
    second = client.get(f"/v1/enquiries/{enquiry_id}/timeline", headers=_demo()).json()
    # A re-read (page refresh / resume) returns the same persisted sequence — no re-run drift.
    assert [e["step"] for e in first["events"]] == [e["step"] for e in second["events"]]


def test_duplicate_submission_is_one_enquiry(client: TestClient) -> None:
    headers = _demo(key=True)
    payload = {"text": "dup", "locale": "en", "destination_warehouse_id": 1}
    a = client.post("/v1/enquiries", headers=headers, json=payload)
    b = client.post("/v1/enquiries", headers=headers, json=payload)
    assert a.json()["id"] == b.json()["id"]  # same idempotency key → one enquiry


def test_duplicate_approval_publishes_once(client: TestClient) -> None:
    enquiry_id = _create(client, "Need 1 air filter element CA-AF-8973 for Corvane Air CA-110 serial 800123")
    first = _approve(client, enquiry_id).json()
    second = _approve(client, enquiry_id).json()
    assert first["already_applied"] is False and second["already_applied"] is True
    enq = client.get(f"/v1/enquiries/{enquiry_id}", headers=_demo()).json()
    recs = sum(1 for m in enq["messages"] if m["kind"] == "recommendation")
    assert enq["status"] == "approved" and recs == 1  # no duplicate reply on replay


def test_unauthorized_access_is_404(client: TestClient) -> None:
    enquiry_id = _create(client, "mine", token="owner")
    for path in (
        f"/v1/enquiries/{enquiry_id}",
        f"/v1/enquiries/{enquiry_id}/timeline",
        f"/v1/staff/enquiries/{enquiry_id}",  # a foreign session can't review it either
    ):
        assert client.get(path, headers=_demo("intruder")).status_code == 404
    # A foreign session approving another session's enquiry is NOT_FOUND (own-session isolation).
    assert _approve(client, enquiry_id, token="intruder").status_code == 404


def test_fixture_mode_completes_without_live_credits(client: TestClient) -> None:
    # Fixture mode spends NO provider credits yet still runs the full workflow to the review
    # pause (honest no-credit path): the enquiry is preserved and progresses, never fabricated
    # live results. If live credits were exhausted this is exactly the preserved fallback.
    settings = client.app.state.settings
    assert settings.ai_mode == "fixture"
    enquiry_id = _create(client, "Need 1 air filter element CA-AF-8973 for Corvane Air CA-110 serial 800123")
    assert client.get(f"/v1/enquiries/{enquiry_id}/progress", headers=_demo()).json()["step"] == "review"
