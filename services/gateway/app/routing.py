"""Maps public gateway paths to internal service paths."""

import re
from collections.abc import Mapping
from dataclasses import dataclass

# Public resource name -> internal service name.
UPSTREAM_ROUTES: Mapping[str, str] = {
    "enquiries": "orchestrator",
    "search": "search",
}

_SAFE_SUB_PATH = re.compile(r"^[A-Za-z0-9\-_./]*$")


@dataclass(frozen=True, slots=True)
class UpstreamTarget:
    """The internal service and path a public request resolves to."""

    service: str
    path: str


def resolve_upstream(resource: str, sub_path: str) -> UpstreamTarget | None:
    """Resolve a public route, rejecting unknown resources and path-traversal attempts."""
    service = UPSTREAM_ROUTES.get(resource)
    if service is None or not _SAFE_SUB_PATH.fullmatch(sub_path):
        return None
    segments = [segment for segment in sub_path.split("/") if segment]
    if any(segment in {".", ".."} for segment in segments):
        return None
    suffix = "/" + "/".join(segments) if segments else ""
    return UpstreamTarget(service=service, path=f"/v1/{resource}{suffix}")
