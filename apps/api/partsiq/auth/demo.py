"""Anonymous demo sessions and reset isolation (foundation 07).

Ported from ``services/gateway/app/demo.py`` and adapted to the single ``partsiq`` package.

A demo session is bound to a verified anonymous Supabase identity (the ``actor``). It is
created with ``generation = 1`` and an access TTL from ``Settings.demo_session_ttl_seconds``
(24 hours by default). Reset is IDEMPOTENT per Idempotency-Key, takes a row lock in the
store, and BUMPS the generation so a background final write that still carries the old
generation is isolated and discarded (ARCHITECTURE section 6). A demo actor can therefore
only ever see its own session's current-generation data.

The datastore and rate limiter are injected so the control flow is testable offline. The
in-memory :class:`InMemoryDemoStore` is a deterministic reference implementation (used by
tests and the fixture demo path); production supplies a PostgreSQL-backed store that holds
the real row lock, cancels prior-generation jobs and schedules Storage cleanup.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID, uuid4

from partsiq.core.contracts import ActorContext, DemoSession
from partsiq.core.errors import PartsIQError
from partsiq.core.settings import Settings


class DemoStore(Protocol):
    async def create_session(self, owner_id: UUID) -> DemoSession: ...

    async def reset_session(self, owner_id: UUID, idempotency_key: UUID) -> DemoSession: ...


# Returns True when the hit is allowed (within limit); False denies the request.
RateLimiter = Callable[[str], Awaitable[bool]]


def _require_identity(actor: ActorContext | None) -> ActorContext:
    if actor is None or actor.user_id is None:
        raise PartsIQError(
            "UNAUTHENTICATED", internal_detail="demo requires an authenticated identity"
        )
    return actor


async def create_demo(
    actor: ActorContext, *, store: DemoStore, rate_limiter: RateLimiter
) -> DemoSession:
    """Create (or resolve) the caller's demo session.

    The rate-limit check runs BEFORE any datastore work so a flood of requests cannot
    create session rows (SECURITY: limiter failure denies new work, never removes it).
    """
    verified = _require_identity(actor)
    if not await rate_limiter(f"demo-create:{verified.user_id}"):
        raise PartsIQError("QUOTA_EXCEEDED", internal_detail="demo creation rate limit")
    return await store.create_session(verified.user_id)


async def reset_demo(actor: ActorContext, key: UUID, *, store: DemoStore) -> DemoSession:
    """Reset the caller's demo session; idempotent per ``key``.

    The store holds the row lock, increments the generation and (in production) cancels old
    jobs + schedules cleanup. Repeating a reset with the same key returns the same
    generation, so a retried request never double-advances the session.
    """
    verified = _require_identity(actor)
    return await store.reset_session(verified.user_id, key)


class InMemoryDemoStore:
    """Deterministic reference store: one current session per owner.

    Honours ``Settings.demo_session_ttl_seconds`` for the access expiry, starts each new
    session at ``generation = 1``, and makes reset idempotent per key while monotonically
    bumping the generation on every new key. This mirrors the PostgreSQL store's observable
    contract without a database.
    """

    def __init__(self, settings: Settings) -> None:
        self._ttl = timedelta(seconds=settings.demo_session_ttl_seconds)
        self._sessions: dict[UUID, DemoSession] = {}  # owner_id -> current session
        self._applied: dict[tuple[UUID, UUID], int] = {}  # (owner, key) -> generation

    def _expiry(self) -> datetime:
        return datetime.now(tz=timezone.utc) + self._ttl

    async def create_session(self, owner_id: UUID) -> DemoSession:
        existing = self._sessions.get(owner_id)
        if existing is not None:
            return existing
        session = DemoSession(id=uuid4(), generation=1, expires_at=self._expiry())
        self._sessions[owner_id] = session
        return session

    async def reset_session(self, owner_id: UUID, idempotency_key: UUID) -> DemoSession:
        applied_key = (owner_id, idempotency_key)
        current = self._sessions.get(owner_id)
        if current is None:
            # Nothing to reset yet: establish a session so the generation has a base.
            current = await self.create_session(owner_id)
        if applied_key in self._applied:
            # Idempotent replay: return the session at the generation this key produced.
            generation = self._applied[applied_key]
            return current.model_copy(update={"generation": generation})
        new_generation = current.generation + 1
        reset = current.model_copy(
            update={"generation": new_generation, "expires_at": self._expiry()}
        )
        self._sessions[owner_id] = reset
        self._applied[applied_key] = new_generation
        return reset
