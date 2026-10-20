"""Supabase JWT verification (foundation 07).

Ported from ``services/gateway/app/auth.py`` and adapted to the single ``partsiq``
package. Verifies a Supabase browser token before any privileged code runs:

* The signing algorithm must be in the explicit allowlist (``RS256``). ``alg=none``,
  a malformed header and an HS256/RS256 confusion attempt are all rejected.
* Signature is checked against a JWKS fetched + cached by key id. An unknown ``kid``
  refreshes the JWKS exactly ONCE (not on every request); a still-unknown key is a
  hard UNAUTHENTICATED failure.
* Issuer, audience and expiry are enforced exactly from ``Settings``
  (``supabase_jwt_issuer`` / ``supabase_jwt_audience``); ``exp``/``sub``/``aud``/``iss``
  are required claims.
* The result carries only the VERIFIED subject and raw claims. Roles are NOT read here:
  a forged ``role``/``roles`` claim is irrelevant because staff membership is resolved
  server-side from the database in :mod:`partsiq.auth.access`.

The JWKS loader is injected so verification is fully testable offline with a throwaway
RSA keypair; production wires the real Supabase JWKS URL. Live Supabase Auth itself is
BLOCKED in this environment and is exercised only through the round-trip keypair.
"""
from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import jwt
from jwt.algorithms import ECAlgorithm, RSAAlgorithm

from partsiq.core.errors import PartsIQError

# kid -> JWK JSON string. Injected so tests supply a local keyset and production wires
# the live Supabase JWKS endpoint behind a bounded-timeout HTTP fetch.
JwksLoader = Callable[[], Awaitable[dict[str, str]]]

DEFAULT_ALGORITHMS: tuple[str, ...] = ("RS256", "ES256")


@dataclass(frozen=True, slots=True)
class VerifiedToken:
    """The verified identity extracted from a Supabase JWT.

    ``subject`` is the Supabase user id (anonymous sign-in for public demos). ``claims``
    are the raw verified claims for auditing/diagnosis only — roles are never trusted
    from them.
    """

    subject: UUID
    claims: dict[str, Any]


class TokenVerifier:
    """Verify Supabase RS256 JWTs against a cached, refresh-once JWKS."""

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks_loader: JwksLoader,
        algorithms: tuple[str, ...] = DEFAULT_ALGORITHMS,
        hs256_secret: str | None = None,
    ) -> None:
        if not issuer:
            raise ValueError("supabase_jwt_issuer must be configured for token verification")
        if not audience:
            raise ValueError("supabase_jwt_audience must be configured for token verification")
        self._issuer = issuer
        self._audience = audience
        self._jwks_loader = jwks_loader
        self._algorithms = algorithms
        # Legacy Supabase projects sign with a shared secret. It is accepted ONLY when the server
        # holds that secret, and an HS256 token is then never checked against a JWKS public key
        # (no HS/RS confusion): the algorithm decides the key source, and both are pinned.
        self._hs256_secret = hs256_secret
        self._jwks: dict[str, str] = {}

    async def _key_for(self, kid: str) -> Any:
        # Refresh the JWKS at most once on an unknown kid; a persistently unknown key id
        # is a hard failure rather than an unbounded refresh loop.
        if kid not in self._jwks:
            self._jwks = await self._jwks_loader()
        jwk = self._jwks.get(kid)
        if jwk is None:
            raise PartsIQError("UNAUTHENTICATED", internal_detail="unknown signing key id")
        if '"EC"' in jwk:
            return ECAlgorithm.from_jwk(jwk)
        return RSAAlgorithm.from_jwk(jwk)

    async def verify(self, token: str) -> VerifiedToken:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise PartsIQError("UNAUTHENTICATED", internal_detail="malformed token") from exc

        # Reject any algorithm not explicitly allowed: 'none', or an HS/RS confusion where
        # the attacker signs with a symmetric key but claims an asymmetric alg.
        alg = header.get("alg")
        if alg == "HS256" and self._hs256_secret:
            key: Any = self._hs256_secret
            algorithms = ["HS256"]
        elif alg in self._algorithms and alg != "HS256":
            key = await self._key_for(str(header.get("kid", "")))
            algorithms = [alg]
        else:
            raise PartsIQError("UNAUTHENTICATED", internal_detail="disallowed algorithm")
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=algorithms,
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "sub", "aud", "iss"]},
            )
        except jwt.PyJWTError as exc:
            raise PartsIQError(
                "UNAUTHENTICATED",
                internal_detail=f"token rejected: {type(exc).__name__}",
            ) from exc

        try:
            subject = UUID(str(claims["sub"]))
        except (KeyError, ValueError) as exc:
            raise PartsIQError("UNAUTHENTICATED", internal_detail="subject is not a UUID") from exc
        return VerifiedToken(subject=subject, claims=claims)


def jwks_from_keyset(keys: list[dict[str, Any]]) -> dict[str, str]:
    """Build the ``kid -> JWK-JSON`` mapping the verifier expects from a JWKS document."""
    return {key["kid"]: json.dumps(key) for key in keys if "kid" in key}
