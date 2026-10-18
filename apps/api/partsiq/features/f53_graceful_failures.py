"""F53 Graceful failures facade (FACADE-ONLY — no endpoints.json entry).

Graceful failure is a cross-cutting guarantee: every error leaves the caller with a safe,
machine-readable ``Problem`` and never a stack trace, a database message, a provider response, a
secret or a private object path. It is already ENFORCED by the error vocabulary this facade
documents and re-exports:

  * Every failure is a :class:`~partsiq.core.errors.PartsIQError` whose ``code`` maps to exactly
    one HTTP status and a fixed, human-safe ``detail`` (:data:`partsiq.core.errors.ERROR_CATALOG`).
    An unexpected exception is mapped to a generic 500/503 Problem, never leaked verbatim.
  * A DB/provider-backed surface that is unavailable (or unwired in this environment) raises a
    CLEAN, retryable ``DEPENDENCY_UNAVAILABLE`` (503) — the established offline pattern — rather
    than fabricating a result. The AI path similarly degrades to ``CREDIT_UNAVAILABLE`` (503) with
    no paid fallback instead of silently charging.
  * ``retryable`` on the Problem tells the client which failures are safe to retry (429/503), so a
    transient outage degrades gracefully instead of corrupting state.

This module performs no I/O; it exists so the guarantee is nameable and testable.
"""
from __future__ import annotations

from partsiq.core.api_models import Problem
from partsiq.core.errors import ERROR_CATALOG, PartsIQError

__all__ = ["ERROR_CATALOG", "PartsIQError", "Problem"]


def is_retryable(code: str) -> bool:
    """Return whether a known error ``code`` is safe for the client to retry (429/503 family).

    An unknown code is treated as NOT retryable (fail closed), so a caller never retries a failure
    the server did not explicitly mark transient.
    """
    entry = ERROR_CATALOG.get(code)
    return bool(entry and entry[2])
