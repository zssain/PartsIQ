"""Public error vocabulary and RFC9457-style Problem construction (foundation 01).

Routes convert a raised :class:`PartsIQError` into the ``Problem`` body defined in
``core.api_models`` (type/title/status/code/detail/request_id/retryable). ``code`` is the
machine-readable contract field; ``request_id`` is for diagnosis. Detail strings are fixed,
human-safe text — they never embed a stack trace, a database message, a provider response,
a secret or a private object path (CONSTRAINTS rule 10). Each code maps to exactly one HTTP
status so no handler reinvents the mapping.
"""
from __future__ import annotations

from uuid import UUID

from .api_models import Problem

# code -> (http_status, title, retryable). The status column matches the VALIDATION
# AND FAILURES table in prompt 01: 401 missing auth, 403 insufficient role, 404 foreign
# scoped resource, 409 stale revision / changed idempotency payload / stale catalogue,
# 413 oversize, 415 wrong media type, 422 invalid typed input, 429 quota, 503 unavailable.
ERROR_CATALOG: dict[str, tuple[int, str, bool]] = {
    "MALFORMED_REQUEST": (400, "Malformed request", False),
    "UNAUTHENTICATED": (401, "Authentication required", False),
    "FORBIDDEN": (403, "Insufficient role", False),
    "NOT_FOUND": (404, "Resource unavailable", False),
    "STALE_REVISION": (409, "Stale revision", False),
    "STALE_CATALOGUE": (409, "Stale catalogue version", False),
    "CONFLICT": (409, "State conflict", False),
    "IDEMPOTENCY_MISMATCH": (409, "Idempotency key reused with a different payload", False),
    "PAYLOAD_TOO_LARGE": (413, "Payload too large", False),
    "UNSUPPORTED_MEDIA_TYPE": (415, "Unsupported media type", False),
    "VALIDATION_FAILED": (422, "Invalid input", False),
    "QUOTA_EXCEEDED": (429, "Too many requests", True),
    "DEPENDENCY_UNAVAILABLE": (503, "A required service is temporarily unavailable", True),
    "CREDIT_UNAVAILABLE": (503, "AI processing is currently unavailable", True),
}

DEFAULT_CODE = "DEPENDENCY_UNAVAILABLE"

# A stable, non-dereferenced type URI namespace (RFC9457 allows an opaque "about:blank"
# or a project URN; we use a URN so clients can switch on code without a live doc fetch).
PROBLEM_TYPE_PREFIX = "urn:partsiq:error:"


class PartsIQError(Exception):
    """An application error carrying a public contract code.

    ``internal_detail`` is server-side only and is never serialized to the client.
    ``detail`` is the safe, human-readable string placed in the Problem body.
    """

    def __init__(
        self,
        code: str,
        *,
        detail: str | None = None,
        internal_detail: str | None = None,
    ) -> None:
        if code not in ERROR_CATALOG:
            code = DEFAULT_CODE
        self.code = code
        self.http_status, title, self.retryable = ERROR_CATALOG[code]
        self.title = title
        self.detail = detail or title
        self.internal_detail = internal_detail
        super().__init__(self.internal_detail or self.detail)


def http_status_for(code: str) -> int:
    """Return the HTTP status for a code, defaulting safely for unknown codes."""
    return ERROR_CATALOG.get(code, ERROR_CATALOG[DEFAULT_CODE])[0]


def build_problem(code: str, request_id: UUID, detail: str | None = None) -> Problem:
    """Construct the RFC9457-style Problem body. Only safe fields are included."""
    if code not in ERROR_CATALOG:
        code = DEFAULT_CODE
    status, title, retryable = ERROR_CATALOG[code]
    return Problem(
        type=f"{PROBLEM_TYPE_PREFIX}{code}",
        title=title,
        status=status,
        code=code,
        detail=detail or title,
        request_id=request_id,
        retryable=retryable,
    )
