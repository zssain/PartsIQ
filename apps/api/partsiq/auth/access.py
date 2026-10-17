"""Verified actors, server-side roles and access control (foundation 07).

Ported from ``services/gateway/app/permissions.py`` (and the actor-construction half of
``services/gateway/app/auth.py``) and adapted to the single ``partsiq`` package.

Two responsibilities:

1. Build a trusted :class:`~partsiq.core.contracts.ActorContext`. The subject comes from a
   verified Supabase token (:mod:`partsiq.auth.tokens`); staff ROLES come from an injected
   DB-sourced lookup. A forged ``role``/``roles`` JWT claim can never grant membership
   because the token's claims are not consulted here. Customer identity never comes from a
   request body ``actor_id``.

2. :func:`require_access` mirrors the database RLS policies (SECURITY access matrix):
   * Demo enquiries are reviewable only by the owner of the matching ACTIVE session
     (same ``session_id`` and ``session_generation``) — a foreign or stale-generation demo
     enquiry returns NOT_FOUND (404) so existence is never leaked.
   * Real enquiries are assigned-only: an admin, or the assigned reviewer. A claimed
     reviewer who is not assigned gets NOT_FOUND (404), not FORBIDDEN (403).
   * ``ASSIGN`` is admin-only; ``IMPORT`` requires admin or catalogue admin — a
     recognised-but-insufficient role gives FORBIDDEN (403).

The access repository, JWKS loader and role provider are injected so the decision logic is
unit-testable without a database or live Supabase. The :class:`AuthVerifier` exposes a
FastAPI-friendly ``async def __call__(request) -> ActorContext`` that a later prompt wires
onto ``app.state.actor_verifier`` (see :func:`partsiq.core.dependencies.require_actor`).
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from partsiq.core.contracts import AccessAction, ActorContext
from partsiq.core.errors import PartsIQError

from .tokens import JwksLoader, TokenVerifier

if TYPE_CHECKING:  # avoid a hard FastAPI import at module load for pure unit tests
    from fastapi import Request

# Only these roles are honoured; anything else a DB row might return is dropped, and the
# order here is stable so ActorContext.roles is deterministic.
STAFF_ROLES: tuple[str, ...] = ("reviewer", "catalogue_admin", "admin")

# user_id (as str) -> staff roles sourced from the operational database.
RoleProvider = Callable[[str], Awaitable[list[str]]]


@dataclass(frozen=True, slots=True)
class EnquiryAccess:
    """The ownership/assignment facts needed to authorise an enquiry action.

    Read through an injected repository so the decision logic below never touches a
    database directly and stays unit-testable.
    """

    enquiry_id: UUID
    owner_id: UUID | None
    session_id: UUID | None
    session_generation: int | None
    assigned_to: UUID | None


AccessRepo = Callable[[UUID], Awaitable[EnquiryAccess | None]]


def _own_active_demo(actor: ActorContext, record: EnquiryAccess) -> bool:
    """True only when the actor owns the enquiry's current (non-reset) demo session."""
    return (
        record.session_id is not None
        and record.owner_id == actor.user_id
        and actor.session_id == record.session_id
        and actor.session_generation == record.session_generation
    )


async def require_access(
    actor: ActorContext, enquiry_id: UUID, action: AccessAction, *, repo: AccessRepo
) -> EnquiryAccess:
    """Authorise ``action`` on ``enquiry_id`` for ``actor``; raise on denial.

    Returns the resolved :class:`EnquiryAccess` so a caller can reuse the loaded facts
    (e.g. to build an ``EnquiryView``) without a second fetch.
    """
    record = await repo(enquiry_id)
    if record is None:
        # Foreign/nonexistent scoped resources are 404, never 403 — existence is not leaked.
        raise PartsIQError("NOT_FOUND", internal_detail="enquiry not found")

    is_admin = "admin" in actor.roles
    is_reviewer = "reviewer" in actor.roles
    is_catalogue_admin = "catalogue_admin" in actor.roles

    if record.session_id is not None:
        # Demo enquiry: only the owner of the matching ACTIVE session may read/review it.
        # A foreign owner/session or a stale generation is reported as NOT_FOUND (404).
        if not _own_active_demo(actor, record):
            raise PartsIQError("NOT_FOUND", internal_detail="foreign or stale demo enquiry")
        return record  # own active demo: read and review allowed (role switching is UI-only)

    # Real enquiry.
    assigned = record.assigned_to is not None and record.assigned_to == actor.user_id
    can_read = is_admin or (assigned and is_reviewer)
    if not can_read:
        # Unassigned reviewer / non-member on a real enquiry: 404, not 403 (no existence leak).
        raise PartsIQError("NOT_FOUND", internal_detail="not assigned")

    if action == AccessAction.ASSIGN and not is_admin:
        raise PartsIQError("FORBIDDEN", internal_detail="assignment is admin-only")
    if action == AccessAction.IMPORT and not (is_admin or is_catalogue_admin):
        raise PartsIQError("FORBIDDEN", internal_detail="import requires catalogue admin")
    return record


async def build_actor(
    *,
    token: str,
    verifier: TokenVerifier,
    role_provider: RoleProvider,
    request_id: UUID | None = None,
    session_id: UUID | None = None,
    session_generation: int | None = None,
) -> ActorContext:
    """Verify ``token`` and assemble a trusted :class:`ActorContext`.

    Roles are taken ONLY from ``role_provider`` (the operational database) and filtered to
    the known staff roles — forged token role claims are ignored by construction.
    """
    verified = await verifier.verify(token)
    db_roles = await role_provider(str(verified.subject))
    roles = [role for role in STAFF_ROLES if role in db_roles]
    return ActorContext(
        user_id=verified.subject,
        request_id=request_id or uuid4(),
        roles=roles,  # type: ignore[arg-type]  # filtered to the Literal set above
        session_id=session_id,
        session_generation=session_generation,
    )


def _bearer_token(request: "Request") -> str:
    header = request.headers.get("authorization") or request.headers.get("Authorization")
    if not header:
        raise PartsIQError("UNAUTHENTICATED", internal_detail="missing Authorization header")
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        raise PartsIQError("UNAUTHENTICATED", internal_detail="expected a Bearer token")
    return value.strip()


def _optional_uuid_header(request: "Request", name: str) -> UUID | None:
    raw = request.headers.get(name)
    if not raw:
        return None
    try:
        return UUID(raw)
    except ValueError as exc:
        raise PartsIQError("UNAUTHENTICATED", internal_detail=f"malformed {name} header") from exc


def _optional_int_header(request: "Request", name: str) -> int | None:
    raw = request.headers.get(name)
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise PartsIQError("UNAUTHENTICATED", internal_detail=f"malformed {name} header") from exc


class AuthVerifier:
    """FastAPI-friendly actor verifier.

    A later prompt builds one from ``Settings`` (issuer/audience), the live JWKS loader and
    the DB role lookup, then assigns it to ``app.state.actor_verifier`` so
    :func:`partsiq.core.dependencies.require_actor` can resolve a trusted actor per request.
    The demo ``session_id`` / ``session_generation`` presented by the browser are advisory
    context; :func:`require_access` still validates them against the stored session.
    """

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks_loader: JwksLoader,
        role_provider: RoleProvider,
    ) -> None:
        self._verifier = TokenVerifier(
            issuer=issuer, audience=audience, jwks_loader=jwks_loader
        )
        self._role_provider = role_provider

    async def __call__(self, request: "Request") -> ActorContext:
        token = _bearer_token(request)
        request_id = _optional_uuid_header(request, "X-Request-Id") or uuid4()
        return await build_actor(
            token=token,
            verifier=self._verifier,
            role_provider=self._role_provider,
            request_id=request_id,
            session_id=_optional_uuid_header(request, "X-Demo-Session-Id"),
            session_generation=_optional_int_header(request, "X-Demo-Session-Generation"),
        )


async def build_actor_from_request(request: "Request", verifier: AuthVerifier) -> ActorContext:
    """Convenience wrapper so routes can resolve an actor without touching internals."""
    return await verifier(request)
