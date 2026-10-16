"""Supabase JWT verification and actor construction.

Contract: ``async def authenticate(token: str) -> ActorContext``.

Rules (prompt 07, F54):
  * Verify issuer, audience, expiry and the allowed signing algorithm against a cached
    JWKS; refresh the JWKS at most once when a key id is unknown.
  * Derive staff roles from the DATABASE, never from JWT claims — a forged ``role`` or
    ``roles`` claim can never grant staff membership.
  * The subject is the verified Supabase user id (anonymous sign-in for public demos).

The JWKS loader and the role provider are injected so verification is fully testable
offline with a throwaway keypair; production wires the real JWKS URL and a DB lookup.
"""
from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import jwt
from jwt.algorithms import RSAAlgorithm

from partsiq_common.contracts import ActorContext
from partsiq_common.errors import PartsIQError

STAFF_ROLES = ("reviewer", "catalogue_admin", "admin")

JwksLoader = Callable[[], Awaitable[dict[str, str]]]  # kid -> JWK JSON string
RoleProvider = Callable[[str], Awaitable[list[str]]]  # user_id -> DB roles


class Authenticator:
    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks_loader: JwksLoader,
        role_provider: RoleProvider,
        algorithms: tuple[str, ...] = ("RS256",),
    ) -> None:
        self._issuer = issuer
        self._audience = audience
        self._jwks_loader = jwks_loader
        self._role_provider = role_provider
        self._algorithms = algorithms
        self._jwks: dict[str, str] = {}

    async def _key_for(self, kid: str):
        if kid not in self._jwks:
            self._jwks = await self._jwks_loader()  # refresh once on unknown kid
        jwk = self._jwks.get(kid)
        if jwk is None:
            raise PartsIQError("UNAUTHENTICATED", internal_detail="unknown signing key id")
        return RSAAlgorithm.from_jwk(jwk)

    async def authenticate(self, token: str, *, request_id: UUID | None = None) -> ActorContext:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise PartsIQError("UNAUTHENTICATED", internal_detail="malformed token") from exc
        # Reject any algorithm we do not explicitly allow (e.g. 'none', HS256 confusion).
        if header.get("alg") not in self._algorithms:
            raise PartsIQError("UNAUTHENTICATED", internal_detail="disallowed algorithm")
        key = await self._key_for(header.get("kid", ""))
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=list(self._algorithms),
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "sub", "aud", "iss"]},
            )
        except jwt.PyJWTError as exc:
            raise PartsIQError("UNAUTHENTICATED", internal_detail=f"token rejected: {type(exc).__name__}") from exc

        user_id = UUID(str(claims["sub"]))
        # Staff membership comes from the database only; JWT role claims are ignored.
        db_roles = await self._role_provider(str(user_id))
        roles = [role for role in db_roles if role in STAFF_ROLES]
        return ActorContext(user_id=user_id, request_id=request_id or uuid4(), roles=roles)


def jwks_from_keyset(keys: list[dict]) -> dict[str, str]:
    """Build the kid -> JWK-JSON mapping the Authenticator expects from a JWKS document."""
    return {key["kid"]: json.dumps(key) for key in keys if "kid" in key}


_authenticator: Authenticator | None = None


def configure_authenticator(authenticator: Authenticator) -> None:
    global _authenticator
    _authenticator = authenticator


async def authenticate(token: str) -> ActorContext:
    if _authenticator is None:
        raise RuntimeError("authenticator is not configured; call configure_authenticator() at startup")
    return await _authenticator.authenticate(token)
