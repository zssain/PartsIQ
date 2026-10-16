import pytest

from app.routing import UpstreamTarget, resolve_upstream


@pytest.mark.parametrize(
    ("resource", "sub_path", "expected"),
    [
        ("enquiries", "", UpstreamTarget("orchestrator", "/v1/enquiries")),
        ("enquiries", "abc-123", UpstreamTarget("orchestrator", "/v1/enquiries/abc-123")),
        ("enquiries", "abc-123/approve/", UpstreamTarget("orchestrator", "/v1/enquiries/abc-123/approve")),
        ("search", "parts", UpstreamTarget("search", "/v1/search/parts")),
    ],
)
def test_resolve_upstream_maps_known_resources(resource: str, sub_path: str, expected: UpstreamTarget) -> None:
    assert resolve_upstream(resource, sub_path) == expected


@pytest.mark.parametrize(
    ("resource", "sub_path"),
    [
        ("admin", ""),
        ("enquiries", "../internal"),
        ("enquiries", "a/./b"),
        ("search", "parts?x=1"),
        ("search", "parts%2F..%2Fsecret"),
    ],
)
def test_resolve_upstream_rejects_unknown_or_unsafe_paths(resource: str, sub_path: str) -> None:
    assert resolve_upstream(resource, sub_path) is None
