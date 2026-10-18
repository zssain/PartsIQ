"""Search / catalogue-read feature routers served over /v1 in fixture mode (F20-F57).

Confirms the mounted read endpoints return real seed-42 data through the fixture catalogue,
and that the whole set of search/catalogue routes is registered.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from partsiq.core.settings import Settings
from partsiq.main import create_app

DEMO = {"X-Demo-Token": "demo-search"}


@pytest.fixture()
def client():
    with TestClient(create_app(Settings(app_env="test", data_source="fixture"))) as c:
        yield c


def test_search_capabilities_reports_fixture_source(client: TestClient) -> None:
    body = client.get("/v1/search/capabilities", headers=DEMO).json()
    assert body["catalogue_source"] == "fixture"
    assert body["lexical"] is True
    # semantic retrieval is off here (BGE-M3/torch not installed) and reported separately.
    assert body["semantic"] is False
    assert body["catalogue_version_id"]


def test_catalogue_browse_returns_active_version_parts(client: TestClient) -> None:
    resp = client.get("/v1/catalogue/parts", headers=DEMO)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) > 0
    first = body["items"][0]
    assert first["part_number"] and first["catalogue_version_id"]


def test_catalogue_browse_is_paginated(client: TestClient) -> None:
    body = client.get("/v1/catalogue/parts", headers=DEMO).json()
    # over-fetch yields a cursor for the next page (the seed-42 catalogue has ~198 parts).
    assert body.get("next_cursor") is not None


def test_search_and_catalogue_routes_are_mounted(client: TestClient) -> None:
    paths = {r.path for r in client.app.routes if getattr(r, "path", "").startswith("/v1")}
    for expected in (
        "/v1/search/capabilities",
        "/v1/catalogue/parts",
        "/v1/catalogue/parts/{part_number}",
        "/v1/enquiries/{enquiry_id}/items/{item_id}/candidates",
        "/v1/enquiries/{enquiry_id}/items/{item_id}/compatibility",
    ):
        assert expected in paths
