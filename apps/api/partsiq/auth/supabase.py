"""Supabase Auth wiring for invited accounts (ADR 0002).

* :class:`SupabaseJwks` — fetches and caches the project's JWKS
  (``{SUPABASE_URL}/auth/v1/.well-known/jwks.json``) with a bounded timeout; the token verifier
  refreshes it at most once per unknown key id.
* :class:`SupabaseDirectory` — the SERVER-SIDE account directory over the Auth admin API using the
  service-role key (never exposed to the browser). Staff roles are stored in each user's
  ``app_metadata.partsiq_roles``, which only the service role can write; the API reads them from
  the directory (not from token claims), so a user cannot grant themselves a role.
* :class:`CompositeVerifier` — ``Authorization: Bearer`` → verified account actor;
  ``X-Demo-Token`` → anonymous demo actor (only when the public demo is enabled). A request that
  carries neither is 401. A bearer token never falls back to demo identity, and a demo token can
  never reach account data (different workspace by construction).
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import httpx

from partsiq.core.errors import PartsIQError

from .actors import AccountActorContext
from .tokens import TokenVerifier, jwks_from_keyset

_TIMEOUT = httpx.Timeout(5.0, connect=3.0)
ROLE_KEY = "partsiq_roles"
_ALLOWED_ROLES = ("reviewer", "catalogue_admin", "admin")


class SupabaseJwks:
    def __init__(self, supabase_url: str) -> None:
        self._url = supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"

    async def __call__(self) -> dict[str, str]:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.get(self._url)
                response.raise_for_status()
                return jwks_from_keyset(response.json().get("keys", []))
        except (httpx.HTTPError, ValueError) as exc:
            raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail=f"jwks fetch failed: {type(exc).__name__}") from exc


class SupabaseDirectory:
    """Auth admin API client (service role). Used for role lookups, invitations and role changes."""

    def __init__(self, settings: Any, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._base = settings.supabase_url.rstrip("/") + "/auth/v1"
        self._key = settings.supabase_service_role_key
        self._transport = transport
        self._cache: dict[str, tuple[float, list[str]]] = {}
        self._ttl = 30.0
        self._redirect = (settings.allowed_origin_list or [""])[0].rstrip("/") + "/login?invited=1"

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=_TIMEOUT,
            transport=self._transport,
            headers={"apikey": self._key, "Authorization": f"Bearer {self._key}"},
        )

    async def roles_for(self, user_id: str) -> list[str]:
        cached = self._cache.get(user_id)
        if cached and time.monotonic() - cached[0] < self._ttl:
            return cached[1]
        try:
            async with self._client() as client:
                response = await client.get(f"{self._base}/admin/users/{user_id}")
                if response.status_code == 404:
                    roles: list[str] = []
                else:
                    response.raise_for_status()
                    meta = (response.json().get("app_metadata") or {})
                    roles = [r for r in _ALLOWED_ROLES if r in (meta.get(ROLE_KEY) or [])]
        except httpx.HTTPError as exc:
            # Fail closed: an unreachable directory grants NO staff role.
            raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail=f"role lookup failed: {type(exc).__name__}") from exc
        self._cache[user_id] = (time.monotonic(), roles)
        return roles

    def _member(self, user: dict[str, Any]) -> Any:
        from partsiq.workspace.records import MemberRecord

        meta = user.get("app_metadata") or {}
        profile = user.get("user_metadata") or {}
        created = _parse(user.get("created_at")) or datetime.now().astimezone()
        return MemberRecord(
            id=UUID(user["id"]),
            email=user.get("email"),
            display_name=str(profile.get("display_name") or user.get("email") or "Account")[:120],
            roles=[r for r in _ALLOWED_ROLES if r in (meta.get(ROLE_KEY) or [])],
            kind="account" if user.get("last_sign_in_at") else "invited",
            created_at=created,
            last_sign_in_at=_parse(user.get("last_sign_in_at")),
        )

    async def list_users(self) -> list[Any]:
        try:
            async with self._client() as client:
                response = await client.get(f"{self._base}/admin/users", params={"page": 1, "per_page": 200})
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPError as exc:
            raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail=f"user list failed: {type(exc).__name__}") from exc
        users = body.get("users", body if isinstance(body, list) else [])
        return [self._member(u) for u in users if not u.get("is_anonymous")]

    async def invite(self, *, email: str, display_name: str | None, roles: list[str]) -> Any:
        try:
            async with self._client() as client:
                response = await client.post(
                    f"{self._base}/invite",
                    params={"redirect_to": self._redirect},
                    json={"email": email, "data": {"display_name": display_name or email.split("@")[0]}},
                )
                if response.status_code in (400, 422):
                    raise PartsIQError("VALIDATION_FAILED", detail="Supabase rejected the invitation (check the email address or whether it is already registered).")
                response.raise_for_status()
                user = response.json()
                if roles:
                    await self._put_roles(client, user["id"], roles, user.get("app_metadata") or {})
                    user.setdefault("app_metadata", {})[ROLE_KEY] = roles
        except httpx.HTTPError as exc:
            raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail=f"invite failed: {type(exc).__name__}") from exc
        return self._member(user)

    async def set_roles(self, user_id: UUID, roles: list[str]) -> None:
        try:
            async with self._client() as client:
                current = await client.get(f"{self._base}/admin/users/{user_id}")
                current.raise_for_status()
                await self._put_roles(client, str(user_id), roles, current.json().get("app_metadata") or {})
        except httpx.HTTPError as exc:
            raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail=f"role update failed: {type(exc).__name__}") from exc
        self._cache.pop(str(user_id), None)

    async def _put_roles(self, client: httpx.AsyncClient, user_id: str, roles: list[str], meta: dict[str, Any]) -> None:
        response = await client.put(f"{self._base}/admin/users/{user_id}", json={"app_metadata": {**meta, ROLE_KEY: roles}})
        response.raise_for_status()


def _parse(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


class AccountVerifier:
    """Verify a Supabase access token and build an :class:`AccountActorContext`."""

    def __init__(self, *, verifier: TokenVerifier, directory: SupabaseDirectory | None) -> None:
        self._verifier = verifier
        self._directory = directory

    async def __call__(self, request: Any) -> AccountActorContext:
        header = request.headers.get("authorization") or ""
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise PartsIQError("UNAUTHENTICATED", internal_detail="expected a Bearer token")
        verified = await self._verifier.verify(token.strip())
        claims = verified.claims
        roles: list[str] = []
        if self._directory is not None and not claims.get("is_anonymous"):
            roles = await self._directory.roles_for(str(verified.subject))
        request_id = getattr(request.state, "request_id", None)
        profile = claims.get("user_metadata") or {}
        return AccountActorContext(
            user_id=verified.subject,
            request_id=request_id if isinstance(request_id, UUID) else uuid4(),
            roles=roles,  # type: ignore[arg-type]
            email=claims.get("email"),
            display_name=(profile.get("display_name") or claims.get("email")),
        )


class CompositeVerifier:
    def __init__(self, *, account: AccountVerifier | None, demo: Any | None) -> None:
        self._account = account
        self._demo = demo

    async def __call__(self, request: Any) -> Any:
        if request.headers.get("authorization"):
            if self._account is None:
                raise PartsIQError("UNAUTHENTICATED", detail="Account sign-in is not configured on this server.")
            return await self._account(request)
        if request.headers.get("x-demo-token"):
            if self._demo is None:
                raise PartsIQError("UNAUTHENTICATED", detail="The public demo is disabled on this server.")
            return await self._demo(request)
        raise PartsIQError("UNAUTHENTICATED", detail="Sign in or start the demo to continue.")


def build_account_verifier(settings: Any, directory: SupabaseDirectory | None) -> AccountVerifier | None:
    if not settings.supabase_url:
        return None
    issuer = settings.supabase_jwt_issuer or settings.supabase_url.rstrip("/") + "/auth/v1"
    verifier = TokenVerifier(
        issuer=issuer,
        audience=settings.supabase_jwt_audience or "authenticated",
        jwks_loader=SupabaseJwks(settings.supabase_url),
        hs256_secret=settings.supabase_jwt_secret or None,
    )
    return AccountVerifier(verifier=verifier, directory=directory)
