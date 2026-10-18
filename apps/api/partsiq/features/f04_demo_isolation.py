"""F04 Demo session isolation facade (helpers ``demo.create_session`` / ``auth.require_demo_session``).

A demo session is bound to the verified anonymous identity and starts at ``generation = 1``.
Isolation: a caller may only ever resolve its OWN current session; asking for a session id that
is not the caller's current one is NOT_FOUND so existence is never leaked. Creation is
rate-limited BEFORE any store work (``partsiq.auth.demo.create_demo``).
"""
from __future__ import annotations

from uuid import UUID

from partsiq.auth.demo import DemoStore, create_demo
from partsiq.core.contracts import ActorContext, DemoSession
from partsiq.core.errors import PartsIQError


async def _always_allowed(_key: str) -> bool:
    """Fixture rate limiter: creation is always allowed offline (no Redis)."""
    return True


async def create_session(actor: ActorContext, *, store: DemoStore) -> DemoSession:
    """Create (or resolve) the caller's demo session at generation 1."""
    return await create_demo(actor, store=store, rate_limiter=_always_allowed)


async def require_demo_session(
    actor: ActorContext, session_id: UUID, *, store: DemoStore
) -> DemoSession:
    """Resolve the caller's own session by id; a foreign/unknown id is NOT_FOUND (no leak).

    The store is keyed by owner, so the caller's current session is created-or-resolved for the
    trusted actor and then checked to equal the requested ``session_id``. A demo caller can
    never read another subject's session.
    """
    current = await create_demo(actor, store=store, rate_limiter=_always_allowed)
    if current.id != session_id:
        raise PartsIQError("NOT_FOUND", internal_detail="demo session not found for caller")
    return current
