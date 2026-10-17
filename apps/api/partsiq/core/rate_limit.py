"""Per-actor / per-demo-session request rate limiting (foundation 08).

Ported and consolidated from ``services/gateway/app/rate_limit.py``. The legacy
``FixedWindowRateLimiter`` counted requests per identity with an atomic ``INCR`` + ``EXPIRE``
pipeline and its boolean adapter failed CLOSED when Redis was unreachable. Prompt 08 step 6
fixes the policy: the limiter uses a bounded atomic counter with a TTL and the API **fails
closed with 503** when its configured limiter is unavailable — a Redis outage never silently
disables the limit and never crashes the request path; it maps to the stable
``DEPENDENCY_UNAVAILABLE`` code instead.

The counter lives behind an injected :class:`RateLimitBackend` port (a thin Redis-like
interface) so the policy is unit-testable without a live Redis. The concrete ``redis.asyncio``
adapter is wired by the API owner and is BLOCKED here (no live Redis in this environment).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .contracts import ActorContext
from .errors import PartsIQError


class RateLimiterUnavailableError(Exception):
    """Raised by a backend that cannot reach its counter store.

    :func:`check_rate_limit` maps this to a 503 ``DEPENDENCY_UNAVAILABLE`` (fail closed) so the
    request is rejected deterministically rather than passed through un-limited or crashing.
    """


@runtime_checkable
class RateLimitBackend(Protocol):
    """Bounded atomic request counter with a TTL (a Redis-like port).

    ``incr`` increments the counter for ``key`` and returns the post-increment count; ``ttl``
    seconds is the window lifetime applied on first write. A concrete implementation uses a
    Redis ``INCR`` + ``EXPIRE`` (ideally a single Lua script, prompt 08 step 6) so the count and
    its expiry are set atomically. On a backend outage it raises
    :class:`RateLimiterUnavailableError`.
    """

    async def incr(self, key: str, ttl_seconds: int) -> int:
        """Atomically increment ``key`` (creating it with ``ttl_seconds``) and return the count."""
        ...


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    reset_after_seconds: int


def rate_limit_identity(actor: ActorContext, action: str) -> str:
    """Build the counter identity for an action.

    A demo caller is bucketed by its ACTIVE session (id + generation) so a reset starts a fresh
    quota and old-generation requests cannot borrow it; a staff/customer caller is bucketed by
    the verified ``user_id``. The identity is derived from the trusted actor only — never from a
    request body (prompt 08: no unverified actor from a request body).
    """
    if actor.session_id is not None:
        return f"{action}:demo:{actor.session_id}:{actor.session_generation}"
    return f"{action}:user:{actor.user_id}"


async def check_rate_limit(
    actor: ActorContext,
    action: str,
    *,
    backend: RateLimitBackend,
    limit: int,
    window_seconds: int = 60,
) -> RateLimitDecision:
    """Count this request against the per-identity window and decide if it is allowed.

    Over the limit raises ``QUOTA_EXCEEDED`` (429). If the backend is unavailable the limiter
    fails CLOSED with ``DEPENDENCY_UNAVAILABLE`` (503) — it never crashes the request path and
    never silently allows an un-limited request (prompt 08 step 6).
    """
    if limit < 1:
        raise ValueError("limit must be at least 1")
    if window_seconds < 1:
        raise ValueError("window_seconds must be at least 1")

    now = int(time.time())
    window_index = now // window_seconds
    key = f"ratelimit:{rate_limit_identity(actor, action)}:{window_index}"
    try:
        # A TTL of two windows lets the key survive a clock-edge read without ever leaking a
        # stale count into the next window's quota.
        count = await backend.incr(key, window_seconds * 2)
    except RateLimiterUnavailableError as exc:
        raise PartsIQError(
            "DEPENDENCY_UNAVAILABLE",
            detail="A required service is temporarily unavailable",
            internal_detail="rate limiter backend unavailable; failing closed",
        ) from exc

    allowed = count <= limit
    decision = RateLimitDecision(
        allowed=allowed,
        limit=limit,
        remaining=max(limit - count, 0),
        reset_after_seconds=window_seconds - (now % window_seconds),
    )
    if not decision.allowed:
        raise PartsIQError(
            "QUOTA_EXCEEDED",
            internal_detail=f"rate limit {limit}/{window_seconds}s exceeded for {action}",
        )
    return decision
