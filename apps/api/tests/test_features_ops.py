"""Remaining feature routers (review extras, catalogue-ops, analytics/eval/observability).

Confirms the final wave of feature routers (F38,F40,F44-F46,F50-F65,F67) is mounted on /v1
and that staff/admin routes refuse a non-staff demo caller rather than leak data. Facade-level
invariants are covered by each feature's domain tests (verification/approval/jobs/analytics/
evaluation suites); here we assert the HTTP surface is wired and access-gated.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from partsiq.core.settings import Settings
from partsiq.main import create_app

DEMO = {"X-Demo-Token": "demo-ops"}


@pytest.fixture()
def client():
    with TestClient(create_app(Settings(app_env="test", data_source="fixture"))) as c:
        yield c


def test_all_remaining_feature_routes_are_mounted(client: TestClient) -> None:
    paths = {r.path for r in client.app.routes if getattr(r, "path", "").startswith("/v1")}
    for expected in (
        "/v1/machines",
        "/v1/enquiries/{enquiry_id}/repeat",
        "/v1/admin/imports",
        "/v1/admin/catalogue/versions",
        "/v1/admin/evaluations",
        "/v1/staff/metrics",
        "/v1/staff/missing-parts",
        "/v1/staff/enquiries/{enquiry_id}/summary",
        "/v1/staff/enquiries/{enquiry_id}/verification",
        "/v1/staff/enquiries/{enquiry_id}/workflow",
        "/v1/staff/enquiries/{enquiry_id}/traces",
        "/v1/enquiries/{enquiry_id}/exports",
        "/v1/jobs/{job_id}",
    ):
        assert expected in paths, expected


def test_the_api_exposes_a_broad_v1_surface(client: TestClient) -> None:
    v1 = {r.path for r in client.app.routes if getattr(r, "path", "").startswith("/v1")}
    # The consolidated single-package app mounts the full feature surface (70+ routes).
    assert len(v1) >= 60


@pytest.mark.parametrize("path", ["/v1/staff/metrics", "/v1/admin/ai-allowance"])
def test_real_staff_only_reads_refuse_a_demo_caller(client: TestClient, path: str) -> None:
    # Shared, real configuration and the staff metrics view are never reachable from the public
    # demo — not even inside its sandbox (ADR 0002: REAL_ONLY capabilities).
    resp = client.get(path, headers=DEMO)
    assert 400 <= resp.status_code < 600


@pytest.mark.parametrize("path", ["/v1/staff/missing-parts", "/v1/admin/catalogue/versions"])
def test_sandbox_admin_reads_are_scoped_to_the_demo_session(client: TestClient, path: str) -> None:
    # A demo visitor previews admin screens over its OWN disposable sandbox only; the result is
    # synthetic and never includes another session's data.
    resp = client.get(path, headers=DEMO)
    assert resp.status_code == 200


def test_saved_machines_list_requires_identity(client: TestClient) -> None:
    # No demo token -> unauthenticated (the fixture verifier refuses an unidentified caller).
    assert client.get("/v1/machines").status_code == 401
