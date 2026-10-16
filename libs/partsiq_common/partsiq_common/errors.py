"""Public error vocabulary and safe error-envelope construction.

Every error returned to a client uses the envelope in docs/CONTRACTS.md:

    {"error": {"code": "STALE_REVISION", "message": "...", "request_id": "..."}}

Messages are fixed, human-safe strings; they never embed a stack trace, a database
message or a credential (CONSTRAINTS.md rule 10). Codes map to a single HTTP status so
routes do not reinvent the mapping per handler.
"""
from __future__ import annotations

from typing import Any

# Canonical error codes and their HTTP status + safe default message.
# (code -> (http_status, default_message))
ERROR_CATALOG: dict[str, tuple[int, str]] = {
    "MALFORMED_REQUEST": (400, "The request could not be understood."),
    "UNAUTHENTICATED": (401, "Sign in to continue."),
    "FORBIDDEN": (403, "You do not have access to this resource."),
    "NOT_FOUND": (404, "The requested resource is unavailable."),
    "STALE_REVISION": (409, "Reload the enquiry and review the current revision."),
    "CONFLICT": (409, "This action conflicts with the current state."),
    "IDEMPOTENCY_MISMATCH": (409, "This idempotency key was used with a different request."),
    "PAYLOAD_TOO_LARGE": (413, "The uploaded content is too large."),
    "UNSUPPORTED_MEDIA_TYPE": (415, "This content type is not supported."),
    "VALIDATION_FAILED": (422, "One or more fields are invalid."),
    "QUOTA_EXCEEDED": (429, "Too many requests. Try again shortly."),
    "DEPENDENCY_UNAVAILABLE": (503, "A required service is temporarily unavailable."),
    "CREDIT_UNAVAILABLE": (503, "AI processing is currently unavailable."),
}

DEFAULT_CODE = "DEPENDENCY_UNAVAILABLE"


class PartsIQError(Exception):
    """An application error with a public code; carries no sensitive detail to the client.

    ``internal_detail`` is for server-side logging only and is never serialized into
    the public envelope.
    """

    def __init__(self, code: str, *, internal_detail: str | None = None, message: str | None = None) -> None:
        if code not in ERROR_CATALOG:
            code = DEFAULT_CODE
        self.code = code
        self.http_status, default_message = ERROR_CATALOG[code]
        self.message = message or default_message
        self.internal_detail = internal_detail
        super().__init__(self.internal_detail or self.message)


def http_status_for(code: str) -> int:
    """Return the HTTP status for a code, defaulting safely for unknown codes."""
    return ERROR_CATALOG.get(code, ERROR_CATALOG[DEFAULT_CODE])[0]


def error_envelope(code: str, request_id: str, message: str | None = None) -> dict[str, Any]:
    """Build the public error body. Only code, a safe message and the request id."""
    if code not in ERROR_CATALOG:
        code = DEFAULT_CODE
    safe_message = message or ERROR_CATALOG[code][1]
    return {"error": {"code": code, "message": safe_message, "request_id": request_id}}
