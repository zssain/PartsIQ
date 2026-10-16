"""Request context middleware: request-ID propagation and access logging."""

import logging
import re
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from partsiq_common.logging import bind_request_id, reset_request_id

REQUEST_ID_HEADER = "X-Request-ID"
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9\-_]{8,64}$")

logger = logging.getLogger("partsiq.access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Accepts a well-formed inbound request ID or generates one, and logs each request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        inbound = request.headers.get(REQUEST_ID_HEADER)
        request_id = inbound if inbound and _VALID_REQUEST_ID.fullmatch(inbound) else uuid4().hex
        request.state.request_id = request_id
        token = bind_request_id(request_id)
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            logger.info(
                "request completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            reset_request_id(token)
