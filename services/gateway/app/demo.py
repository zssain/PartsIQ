"""Public demo sessions on anonymous Supabase identities.

Contracts:
    async def create_demo(actor: ActorContext) -> DemoSession
    async def reset_demo(actor: ActorContext, key: UUID) -> DemoSession

Rules (prompt 07, F04/F05):
  * A session is bound to the verified anonymous identity in ``actor``.
  * Rate-limit BEFORE any database work, so flooding cannot create session rows.
  * Reset takes a row lock, increments the generation, and is idempotent per
    Idempotency-Key — repeating a reset returns the same generation (and cancels prior
    generation jobs + enqueues Storage cleanup, handled by the repository).

The datastore and rate limiter are injected so the control flow is testable offline.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol
from uuid import UUID

from partsiq_common.contracts import ActorContext, DemoSession
from partsiq_common.errors import PartsIQError


class DemoStore(Protocol):
    async def create_session(self, owner_id: UUID) -> DemoSession: ...

    async def reset_session(self, owner_id: UUID, idempotency_key: UUID) -> DemoSession: ...


# Returns True when the hit is allowed (within limit).
RateLimiter = Callable[[str], Awaitable[bool]]


async def create_demo(actor: ActorContext, *, store: DemoStore, rate_limiter: RateLimiter) -> DemoSession:
    if actor is None or actor.user_id is None:  # must be an authenticated (anonymous) identity
        raise PartsIQError("UNAUTHENTICATED", internal_detail="demo requires an authenticated identity")
    # Rate limit BEFORE touching the database.
    if not await rate_limiter(f"demo-create:{actor.user_id}"):
        raise PartsIQError("QUOTA_EXCEEDED", internal_detail="demo creation rate limit")
    return await store.create_session(actor.user_id)


async def reset_demo(actor: ActorContext, key: UUID, *, store: DemoStore) -> DemoSession:
    if actor is None or actor.user_id is None:
        raise PartsIQError("UNAUTHENTICATED", internal_detail="demo requires an authenticated identity")
    # Idempotent under the key; the repository holds the row lock and increments generation.
    return await store.reset_session(actor.user_id, key)
