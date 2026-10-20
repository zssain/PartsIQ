"""Invited-account authentication (ADR 0002): Supabase JWT verification and directory roles.

Offline: a throwaway EC key / HS secret and an httpx MockTransport stand in for Supabase. This
proves the verification and role-sourcing logic; it is NOT evidence that a live Supabase project
was reached (that check is reported separately as blocked until credentials are provided).
"""
from __future__ import annotations

import json
import time
from types import SimpleNamespace
from uuid import uuid4

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from partsiq.auth.actors import AccountActorContext, DemoActorContext, actor_kind
from partsiq.auth.supabase import AccountVerifier, CompositeVerifier, SupabaseDirectory
from partsiq.auth.tokens import TokenVerifier
from partsiq.core.errors import PartsIQError

ISS = "https://example.supabase.co/auth/v1"


def _ec_key():
    private = ec.generate_private_key(ec.SECP256R1())
    jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(private.public_key()))
    jwk["kid"] = "k1"
    return private, jwk


def _token(key, alg: str, sub: str, **claims) -> str:
    payload = {"sub": sub, "aud": "authenticated", "iss": ISS, "exp": int(time.time()) + 300, **claims}
    return jwt.encode(payload, key, algorithm=alg, headers={"kid": "k1"})


async def test_es256_token_verifies_via_jwks_and_alg_confusion_is_refused() -> None:
    private, jwk = _ec_key()

    async def loader():
        return {"k1": json.dumps(jwk)}

    verifier = TokenVerifier(issuer=ISS, audience="authenticated", jwks_loader=loader)
    sub = str(uuid4())
    verified = await verifier.verify(_token(private, "ES256", sub))
    assert str(verified.subject) == sub
    # HS256 is refused when the server holds no shared secret (no HS/ES confusion).
    with pytest.raises(PartsIQError):
        await verifier.verify(_token("not-the-key", "HS256", sub))
    # alg=none is refused.
    unsigned = jwt.encode({"sub": sub, "aud": "authenticated", "iss": ISS, "exp": int(time.time()) + 60}, key=None, algorithm="none")
    with pytest.raises(PartsIQError):
        await verifier.verify(unsigned)


async def test_hs256_only_with_the_server_secret_and_expiry_enforced() -> None:
    async def loader():
        return {}

    verifier = TokenVerifier(issuer=ISS, audience="authenticated", jwks_loader=loader, hs256_secret="server-side-secret-value-123456")
    sub = str(uuid4())
    assert str((await verifier.verify(_token("server-side-secret-value-123456", "HS256", sub))).subject) == sub
    with pytest.raises(PartsIQError):
        await verifier.verify(_token("wrong-secret-wrong-secret-12345", "HS256", sub))
    expired = jwt.encode({"sub": sub, "aud": "authenticated", "iss": ISS, "exp": int(time.time()) - 10}, "server-side-secret-value-123456", algorithm="HS256")
    with pytest.raises(PartsIQError):
        await verifier.verify(expired)


def _directory(handler) -> SupabaseDirectory:
    settings = SimpleNamespace(supabase_url="https://example.supabase.co", supabase_service_role_key="service-role", allowed_origin_list=["https://app.example"])
    return SupabaseDirectory(settings, transport=httpx.MockTransport(handler))


async def test_roles_come_from_the_directory_not_the_token() -> None:
    user_id = str(uuid4())

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer service-role"
        return httpx.Response(200, json={"id": user_id, "invited_at": "2026-10-20T00:00:00Z", "app_metadata": {"partsiq_roles": ["reviewer", "superuser"]}})

    directory = _directory(handler)

    async def loader():
        return {}

    account = AccountVerifier(verifier=TokenVerifier(issuer=ISS, audience="authenticated", jwks_loader=loader, hs256_secret="s" * 32), directory=directory)
    token = _token("s" * 32, "HS256", user_id, app_metadata={"partsiq_roles": ["admin"]}, role="service_role", email="r@example.test")
    request = SimpleNamespace(headers={"authorization": f"Bearer {token}"}, state=SimpleNamespace())
    actor = await account(request)
    assert isinstance(actor, AccountActorContext) and actor_kind(actor) == "account"
    assert actor.roles == ["reviewer"]  # forged claim and unknown role ignored
    assert actor.email == "r@example.test"


async def _account_with(user: dict) -> AccountVerifier:
    async def loader():
        return {}

    directory = _directory(lambda request: httpx.Response(200, json=user))
    return AccountVerifier(verifier=TokenVerifier(issuer=ISS, audience="authenticated", jwks_loader=loader, hs256_secret="s" * 32), directory=directory)


async def test_self_registered_accounts_are_refused_even_with_public_signup_on() -> None:
    user_id = str(uuid4())
    # A user who signed up publicly: no invited_at, no server-set marker, no role. A forged
    # app_metadata claim in the token must not help (claims are never trusted for access).
    account = await _account_with({"id": user_id, "app_metadata": {}, "invited_at": None})
    token = _token("s" * 32, "HS256", user_id, app_metadata={"partsiq_invited": True, "partsiq_roles": ["admin"]})
    with pytest.raises(PartsIQError) as exc:
        await account(SimpleNamespace(headers={"authorization": f"Bearer {token}"}, state=SimpleNamespace()))
    assert exc.value.code == "FORBIDDEN"


@pytest.mark.parametrize("user", [
    {"invited_at": "2026-10-20T00:00:00Z", "app_metadata": {}},          # created by /invite
    {"invited_at": None, "app_metadata": {"partsiq_invited": True}},     # provisioned by an admin
    {"invited_at": None, "app_metadata": {"partsiq_roles": ["reviewer"]}},  # staff role implies it
])
async def test_invited_accounts_are_admitted(user: dict) -> None:
    user_id = str(uuid4())
    account = await _account_with({"id": user_id, **user})
    actor = await account(SimpleNamespace(headers={"authorization": f"Bearer {_token('s' * 32, 'HS256', user_id)}"}, state=SimpleNamespace()))
    assert str(actor.user_id) == user_id


async def test_anonymous_supabase_sessions_cannot_use_the_account_workspace() -> None:
    user_id = str(uuid4())
    account = await _account_with({"id": user_id, "app_metadata": {"partsiq_invited": True}})
    token = _token("s" * 32, "HS256", user_id, is_anonymous=True)
    with pytest.raises(PartsIQError) as exc:
        await account(SimpleNamespace(headers={"authorization": f"Bearer {token}"}, state=SimpleNamespace()))
    assert exc.value.code == "FORBIDDEN"


async def test_directory_outage_fails_closed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    with pytest.raises(PartsIQError) as exc:
        await _directory(handler).roles_for(str(uuid4()))
    assert exc.value.code == "DEPENDENCY_UNAVAILABLE"


async def test_invite_sets_roles_through_the_admin_api_only() -> None:
    calls = []
    new_id = str(uuid4())

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/invite"):
            return httpx.Response(200, json={"id": new_id, "email": "n@example.test", "app_metadata": {}, "created_at": "2026-10-20T00:00:00Z"})
        return httpx.Response(200, json={"id": new_id})

    member = await _directory(handler).invite(email="n@example.test", display_name="New", roles=["reviewer"])
    assert member.roles == ["reviewer"] and member.kind == "invited"
    assert ("POST", "/auth/v1/invite") in calls and ("PUT", f"/auth/v1/admin/users/{new_id}") in calls


async def test_composite_verifier_keeps_bearer_and_demo_apart() -> None:
    class Demo:
        async def __call__(self, request):
            return DemoActorContext(user_id=uuid4(), request_id=uuid4(), roles=[], session_id=uuid4(), session_generation=1)

    composite = CompositeVerifier(account=None, demo=Demo())
    demo_actor = await composite(SimpleNamespace(headers={"x-demo-token": "abc"}, state=SimpleNamespace()))
    assert actor_kind(demo_actor) == "demo" and demo_actor.roles == []
    # A bearer token never falls back to the demo identity.
    with pytest.raises(PartsIQError) as exc:
        await composite(SimpleNamespace(headers={"authorization": "Bearer x", "x-demo-token": "abc"}, state=SimpleNamespace()))
    assert exc.value.code == "UNAUTHENTICATED"
    with pytest.raises(PartsIQError):
        await composite(SimpleNamespace(headers={}, state=SimpleNamespace()))
