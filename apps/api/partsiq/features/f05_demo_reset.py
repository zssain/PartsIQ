"""F05 Demo reset facade (helper ``demo.reset_session``).

Reset is idempotent per ``Idempotency-Key`` and BUMPS the session generation so any background
write still carrying the old generation is isolated and discarded. The caller may only reset its
OWN current session; a foreign/unknown session id is NOT_FOUND. The store holds the row lock and
the generation bump (``partsiq.auth.demo.reset_demo``).
"""
from __future__ import annotations

from uuid import UUID

from partsiq.auth.demo import DemoStore, create_demo, reset_demo
from partsiq.core.contracts import ActorContext, DemoSession
from partsiq.core.errors import PartsIQError


async def _always_allowed(_key: str) -> bool:
    return True


async def reset_session(
    actor: ActorContext, session_id: UUID, key: UUID, *, store: DemoStore
) -> DemoSession:
    """Reset the caller's own session, bumping its generation; idempotent per ``key``.

    The requested ``session_id`` must be the caller's current session (else NOT_FOUND, no leak).
    Reset is scoped to the trusted actor so one caller can never reset another's session.
    """
    current = await create_demo(actor, store=store, rate_limiter=_always_allowed)
    if current.id != session_id:
        raise PartsIQError("NOT_FOUND", internal_detail="demo session not found for caller")
    return await reset_demo(actor, key, store=store)
