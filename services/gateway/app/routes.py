"""Public gateway routes. Every request is authenticated, rate limited, then forwarded."""

import logging

import httpx
from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse

from app.proxy import (
    RequestBodyTooLargeError,
    build_forward_headers,
    filter_response_headers,
    read_limited_body,
)
from app.rate_limit import RateLimiterUnavailableError, RateLimitResult
from app.routing import resolve_upstream
from app.security import is_valid_api_key, key_fingerprint

logger = logging.getLogger("partsiq.gateway")

router = APIRouter(prefix="/api/v1", tags=["gateway"])

_FORWARDED_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]


def _error(request: Request, status_code: int, error: str, message: str, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "message": message, "request_id": request.state.request_id},
        headers=headers,
    )


def _rate_limit_headers(result: RateLimitResult) -> dict[str, str]:
    return {
        "X-RateLimit-Limit": str(result.limit),
        "X-RateLimit-Remaining": str(result.remaining),
        "X-RateLimit-Reset": str(result.reset_after_seconds),
    }


@router.api_route("/{resource}", methods=_FORWARDED_METHODS)
async def forward_collection(resource: str, request: Request) -> Response:
    """Forward a request addressed to a resource collection, such as /api/v1/enquiries."""
    return await _forward(resource, "", request)


@router.api_route("/{resource}/{sub_path:path}", methods=_FORWARDED_METHODS)
async def forward_nested(resource: str, sub_path: str, request: Request) -> Response:
    """Forward a request addressed to a nested path, such as /api/v1/enquiries/{id}."""
    return await _forward(resource, sub_path, request)


async def _forward(resource: str, sub_path: str, request: Request) -> Response:
    """Authenticate, rate limit and forward a request to the owning internal service."""
    state = request.app.state

    api_key = request.headers.get("X-API-Key")
    if api_key is None or not is_valid_api_key(api_key, state.api_keys):
        return _error(
            request,
            status.HTTP_401_UNAUTHORIZED,
            "unauthorized",
            "A valid X-API-Key header is required.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    fingerprint = key_fingerprint(api_key)

    target = resolve_upstream(resource, sub_path)
    if target is None:
        return _error(request, status.HTTP_404_NOT_FOUND, "not_found", "The requested resource does not exist.")

    try:
        limit_result = await state.rate_limiter.hit(fingerprint)
    except RateLimiterUnavailableError:
        logger.error("rate limiter unavailable; rejecting request", exc_info=True)
        return _error(request, status.HTTP_503_SERVICE_UNAVAILABLE, "unavailable", "Service temporarily unavailable.")

    limit_headers = _rate_limit_headers(limit_result)
    if not limit_result.allowed:
        return _error(
            request,
            status.HTTP_429_TOO_MANY_REQUESTS,
            "rate_limited",
            "Too many requests. Retry after the indicated interval.",
            headers={**limit_headers, "Retry-After": str(limit_result.reset_after_seconds)},
        )

    try:
        body = await read_limited_body(request, state.settings.max_request_body_bytes)
    except RequestBodyTooLargeError:
        return _error(
            request,
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            "payload_too_large",
            "The request body exceeds the permitted size.",
            headers=limit_headers,
        )

    upstream_url = state.upstreams[target.service] + target.path
    try:
        upstream_response = await state.http_client.request(
            method=request.method,
            url=upstream_url,
            params=list(request.query_params.multi_items()),
            headers=build_forward_headers(
                request.headers,
                request_id=request.state.request_id,
                client_fingerprint=fingerprint,
            ),
            content=body,
        )
    except httpx.TimeoutException:
        logger.warning("upstream timed out", extra={"upstream": target.service})
        return _error(request, status.HTTP_504_GATEWAY_TIMEOUT, "upstream_timeout", "The service did not respond in time.", headers=limit_headers)
    except httpx.HTTPError:
        logger.warning("upstream unreachable", extra={"upstream": target.service}, exc_info=True)
        return _error(request, status.HTTP_503_SERVICE_UNAVAILABLE, "upstream_unavailable", "The service is currently unavailable.", headers=limit_headers)

    response = Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=filter_response_headers(upstream_response.headers),
    )
    response.headers.update(limit_headers)
    return response
