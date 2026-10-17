"""Dependency container and FastAPI providers (foundation 01).

The container is assembled once in the application lifespan and stored on
``app.state.container``. Adapters (database, AI client, storage, catalogue, jobs) are
injected here so unit tests can supply deterministic fakes and integration tests can
supply disposable services. Later prompts add their adapters to this container; they do
not reach for module-level globals.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import Request

from .errors import PartsIQError
from .settings import Settings

if TYPE_CHECKING:  # avoid importing asyncpg-backed types at module import time
    from .contracts import ActorContext
    from .db import Database


@dataclass
class AppContainer:
    """Process-wide injected dependencies. Grown additively by later prompts."""

    settings: Settings
    database: "Database | None" = None


def get_container(request: Request) -> AppContainer:
    container = getattr(request.app.state, "container", None)
    if container is None:  # pragma: no cover - guards misconfiguration
        raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="container not initialized")
    return container


def get_settings(request: Request) -> Settings:
    return get_container(request).settings


def get_database(request: Request) -> "Database":
    container = get_container(request)
    if container.database is None:
        raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="database not configured")
    return container.database


async def require_actor(request: Request) -> "ActorContext":
    """Resolve a verified actor.

    Foundation 01 has no authentication wired yet; real JWT verification and demo-session
    resolution arrive in prompt 07 (``partsiq.auth``). Until then this refuses rather than
    trust an unverified identity, keeping the no-spoofable-actor invariant intact.
    """
    verifier = getattr(request.app.state, "actor_verifier", None)
    if verifier is None:
        raise PartsIQError("UNAUTHENTICATED", internal_detail="auth not wired (prompt 07)")
    return await verifier(request)
