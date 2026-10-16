"""Request and response transformation for forwarding traffic to internal services."""

from starlette.datastructures import Headers
from starlette.requests import Request

import httpx

from partsiq_common.middleware import REQUEST_ID_HEADER

CLIENT_FINGERPRINT_HEADER = "X-Client-Fingerprint"

_HOP_BY_HOP_HEADERS = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
    }
)

# Credentials terminate at the gateway; internal services never receive them.
_STRIPPED_REQUEST_HEADERS = _HOP_BY_HOP_HEADERS | {
    "host",
    "content-length",
    "x-api-key",
    "cookie",
    "authorization",
    REQUEST_ID_HEADER.lower(),
    CLIENT_FINGERPRINT_HEADER.lower(),
}

# httpx decodes compressed bodies, so encoding and length headers must be recomputed downstream.
_STRIPPED_RESPONSE_HEADERS = _HOP_BY_HOP_HEADERS | {"content-length", "content-encoding", "server"}


class RequestBodyTooLargeError(Exception):
    """Raised when a request body exceeds the configured limit."""


async def read_limited_body(request: Request, limit: int) -> bytes:
    """Read the request body, aborting as soon as it exceeds the limit."""
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > limit:
        raise RequestBodyTooLargeError
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > limit:
            raise RequestBodyTooLargeError
        chunks.append(chunk)
    return b"".join(chunks)


def build_forward_headers(incoming: Headers, *, request_id: str, client_fingerprint: str) -> dict[str, str]:
    """Copy safe client headers and attach trusted gateway-generated context headers."""
    headers = {
        name: value for name, value in incoming.items() if name.lower() not in _STRIPPED_REQUEST_HEADERS
    }
    headers[REQUEST_ID_HEADER] = request_id
    headers[CLIENT_FINGERPRINT_HEADER] = client_fingerprint
    return headers


def filter_response_headers(headers: httpx.Headers) -> dict[str, str]:
    """Return upstream response headers that are safe to relay to the client."""
    return {name: value for name, value in headers.items() if name.lower() not in _STRIPPED_RESPONSE_HEADERS}
