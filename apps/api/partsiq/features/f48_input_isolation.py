"""F48 Input isolation facade (FACADE-ONLY — no endpoints.json entry).

Input isolation is a cross-cutting guarantee, not a new route: every request's data is isolated to
the caller that submitted it. It is already ENFORCED, not invented here, by the surfaces this
facade documents and re-exports so a caller can assert the guarantee without reaching into each
module:

  * Identity is never client-supplied. Ownership is derived from the verified
    :class:`~partsiq.core.contracts.ActorContext` (``user_id`` plus, for a demo, the active
    ``session_id``/generation), never from a request body or header, so a request can never claim
    to be another user. See :func:`partsiq.core.dependencies.require_actor` and
    :func:`partsiq.auth.access.require_access` (a foreign/stale resource is NOT_FOUND, never a 403
    that leaks existence).
  * Bodies are validated at the boundary. :func:`partsiq.core.dependencies.typed_body` parses each
    request with the strict, ``extra='forbid'`` kit contract, so an unknown or mistyped field is a
    422 before any domain code runs — one request's shape can never bleed into another's handler.
  * Writes are idempotent + rate-isolated per actor. The ``Idempotency-Key`` and the per-actor rate
    limiter scope a mutation to its own caller.

This module performs no I/O; it exists so the guarantee is nameable and testable.
"""
from __future__ import annotations

from partsiq.auth.access import require_access
from partsiq.core.dependencies import require_actor, typed_body

__all__ = ["require_actor", "require_access", "typed_body"]
