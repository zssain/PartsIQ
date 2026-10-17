"""Foundation 07 acceptance: authentication, ownership and demo isolation.

Fully offline and deterministic. A throwaway RSA keypair generated IN THIS TEST backs a
local JWKS, so Supabase JWT verification (issuer / audience / expiry / allowed algorithm,
unknown-kid refresh-once, DB-sourced roles) is exercised with REAL signatures — the same
round-trip approach as the legacy gateway test_07. Permissions and demo flows run against
injected in-memory fakes. Live Supabase Auth and the live roles DB are BLOCKED here and are
integration-only; nothing hosted is faked.

Ported from services/gateway/tests/features/{test_f03,test_f04,test_f05,test_f54}.py and
tests/foundations/test_07.py. Covers F03/F04/F05/F54.
"""
from __future__ import annotations

import json
import time
import unittest
from datetime import datetime, timezone
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from partsiq.auth.access import (
    AuthVerifier,
    EnquiryAccess,
    build_actor,
    build_actor_from_request,
    require_access,
)
from partsiq.auth.demo import InMemoryDemoStore, create_demo, reset_demo
from partsiq.auth.tokens import TokenVerifier, jwks_from_keyset
from partsiq.core.contracts import AccessAction, ActorContext, DemoSession
from partsiq.core.errors import PartsIQError
from partsiq.core.settings import Settings

ISS = "https://proj.supabase.co/auth/v1"
AUD = "authenticated"
KID = "test-kid"

# Real keypair minted in-process; the public half becomes the local JWKS.
_PRIV = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_JWK = json.loads(RSAAlgorithm.to_jwk(_PRIV.public_key()))
_JWK.update({"kid": KID, "alg": "RS256", "use": "sig"})
_JWKS = jwks_from_keyset([_JWK])


def make_token(sub, *, iss=ISS, aud=AUD, exp_delta=3600, kid=KID, alg="RS256", extra=None):
    now = int(time.time())
    claims = {"sub": sub, "iss": iss, "aud": aud, "iat": now, "exp": now + exp_delta}
    if extra:
        claims.update(extra)
    if alg == "none":
        return jwt.encode(claims, "", algorithm="none")
    return jwt.encode(claims, _PRIV, algorithm=alg, headers={"kid": kid})


def _verifier(loader=None):
    async def default_loader():
        return _JWKS

    return TokenVerifier(issuer=ISS, audience=AUD, jwks_loader=loader or default_loader)


def _role_provider(roles=()):
    async def provider(_user_id):
        return list(roles)

    return provider


async def _authenticate(token, *, roles=(), loader=None, request_id=None):
    return await build_actor(
        token=token,
        verifier=_verifier(loader=loader),
        role_provider=_role_provider(roles),
        request_id=request_id,
    )


# --- JWT verification (F54) -------------------------------------------------


class JwtVerification(unittest.IsolatedAsyncioTestCase):
    async def test_valid_token_authenticates(self) -> None:
        uid = str(uuid4())
        actor = await _authenticate(make_token(uid))
        self.assertEqual(str(actor.user_id), uid)

    async def test_expired_token_rejected(self) -> None:
        with self.assertRaises(PartsIQError) as ctx:
            await _authenticate(make_token(str(uuid4()), exp_delta=-10))
        self.assertEqual(ctx.exception.code, "UNAUTHENTICATED")

    async def test_wrong_issuer_rejected(self) -> None:
        with self.assertRaises(PartsIQError) as ctx:
            await _authenticate(make_token(str(uuid4()), iss="https://evil/auth"))
        self.assertEqual(ctx.exception.code, "UNAUTHENTICATED")

    async def test_wrong_audience_rejected(self) -> None:
        with self.assertRaises(PartsIQError) as ctx:
            await _authenticate(make_token(str(uuid4()), aud="other"))
        self.assertEqual(ctx.exception.code, "UNAUTHENTICATED")

    async def test_none_algorithm_rejected(self) -> None:
        with self.assertRaises(PartsIQError) as ctx:
            await _authenticate(make_token(str(uuid4()), alg="none"))
        self.assertEqual(ctx.exception.code, "UNAUTHENTICATED")

    async def test_malformed_token_rejected(self) -> None:
        with self.assertRaises(PartsIQError) as ctx:
            await _authenticate("not-a-jwt")
        self.assertEqual(ctx.exception.code, "UNAUTHENTICATED")

    async def test_non_uuid_subject_rejected(self) -> None:
        with self.assertRaises(PartsIQError) as ctx:
            await _authenticate(make_token("not-a-uuid"))
        self.assertEqual(ctx.exception.code, "UNAUTHENTICATED")

    async def test_forged_role_claim_is_ignored(self) -> None:
        # DB provider returns nothing, so a forged role/roles claim grants nothing.
        actor = await _authenticate(
            make_token(str(uuid4()), extra={"role": "admin", "roles": ["admin"]}),
            roles=[],
        )
        self.assertEqual(actor.roles, [])

    async def test_roles_come_from_database(self) -> None:
        actor = await _authenticate(make_token(str(uuid4())), roles=["reviewer"])
        self.assertEqual(actor.roles, ["reviewer"])

    async def test_db_roles_filtered_to_known_staff_roles(self) -> None:
        # An unknown DB role string is dropped; known roles survive in a stable order.
        actor = await _authenticate(
            make_token(str(uuid4())), roles=["superuser", "admin", "reviewer"]
        )
        self.assertEqual(actor.roles, ["reviewer", "admin"])

    async def test_unknown_kid_refreshes_once_then_fails(self) -> None:
        calls = {"n": 0}

        async def loader():
            calls["n"] += 1
            return _JWKS  # never contains the 'ghost' kid

        with self.assertRaises(PartsIQError) as ctx:
            await _authenticate(make_token(str(uuid4()), kid="ghost"), loader=loader)
        self.assertEqual(ctx.exception.code, "UNAUTHENTICATED")
        self.assertEqual(calls["n"], 1)  # refreshed exactly once, not per request

    async def test_missing_issuer_config_rejected(self) -> None:
        async def loader():
            return _JWKS

        with self.assertRaises(ValueError):
            TokenVerifier(issuer="", audience=AUD, jwks_loader=loader)


# --- actor verifier over a request (F54) ------------------------------------


class _FakeHeaders:
    def __init__(self, data):
        self._data = {k.lower(): v for k, v in data.items()}

    def get(self, name, default=None):
        return self._data.get(name.lower(), default)


class _FakeRequest:
    def __init__(self, headers):
        self.headers = _FakeHeaders(headers)


def _auth_verifier(roles=()):
    async def loader():
        return _JWKS

    return AuthVerifier(
        issuer=ISS, audience=AUD, jwks_loader=loader, role_provider=_role_provider(roles)
    )


class RequestActorVerifier(unittest.IsolatedAsyncioTestCase):
    async def test_bearer_token_builds_actor_with_demo_context(self) -> None:
        uid = str(uuid4())
        session = uuid4()
        req = _FakeRequest(
            {
                "Authorization": f"Bearer {make_token(uid)}",
                "X-Demo-Session-Id": str(session),
                "X-Demo-Session-Generation": "3",
            }
        )
        actor = await build_actor_from_request(req, _auth_verifier(roles=["reviewer"]))
        self.assertEqual(str(actor.user_id), uid)
        self.assertEqual(actor.roles, ["reviewer"])
        self.assertEqual(actor.session_id, session)
        self.assertEqual(actor.session_generation, 3)

    async def test_missing_authorization_header_is_unauthenticated(self) -> None:
        with self.assertRaises(PartsIQError) as ctx:
            await _auth_verifier()(_FakeRequest({}))
        self.assertEqual(ctx.exception.code, "UNAUTHENTICATED")

    async def test_non_bearer_scheme_is_unauthenticated(self) -> None:
        req = _FakeRequest({"Authorization": "Basic abc123"})
        with self.assertRaises(PartsIQError) as ctx:
            await _auth_verifier()(req)
        self.assertEqual(ctx.exception.code, "UNAUTHENTICATED")

    async def test_malformed_demo_session_header_is_unauthenticated(self) -> None:
        req = _FakeRequest(
            {
                "Authorization": f"Bearer {make_token(str(uuid4()))}",
                "X-Demo-Session-Id": "not-a-uuid",
            }
        )
        with self.assertRaises(PartsIQError) as ctx:
            await _auth_verifier()(req)
        self.assertEqual(ctx.exception.code, "UNAUTHENTICATED")


# --- access control + demo isolation (F03 / F04 / F54) ----------------------


def _actor(roles=(), session_id=None, generation=None):
    return ActorContext(
        user_id=uuid4(),
        request_id=uuid4(),
        roles=list(roles),
        session_id=session_id,
        session_generation=generation,
    )


def _repo(record):
    async def repo(_enquiry_id):
        return record

    return repo


class AccessControl(unittest.IsolatedAsyncioTestCase):
    async def test_own_active_demo_allowed(self) -> None:
        sid = uuid4()
        actor = _actor(session_id=sid, generation=2)
        record = EnquiryAccess(uuid4(), actor.user_id, sid, 2, None)
        resolved = await require_access(
            actor, record.enquiry_id, AccessAction.REVIEW, repo=_repo(record)
        )
        self.assertEqual(resolved, record)  # returns the loaded facts for reuse

    async def test_foreign_demo_is_not_found(self) -> None:
        actor = _actor(session_id=uuid4(), generation=1)
        record = EnquiryAccess(uuid4(), uuid4(), uuid4(), 1, None)  # different owner/session
        with self.assertRaises(PartsIQError) as ctx:
            await require_access(actor, record.enquiry_id, AccessAction.READ, repo=_repo(record))
        self.assertEqual(ctx.exception.code, "NOT_FOUND")
        self.assertEqual(ctx.exception.http_status, 404)

    async def test_stale_generation_demo_is_not_found(self) -> None:
        sid = uuid4()
        actor = _actor(session_id=sid, generation=2)  # current record is generation 3
        record = EnquiryAccess(uuid4(), actor.user_id, sid, 3, None)
        with self.assertRaises(PartsIQError) as ctx:
            await require_access(actor, record.enquiry_id, AccessAction.READ, repo=_repo(record))
        self.assertEqual(ctx.exception.http_status, 404)

    async def test_assigned_reviewer_can_review_real_enquiry(self) -> None:
        actor = _actor(roles=["reviewer"])
        record = EnquiryAccess(uuid4(), None, None, None, actor.user_id)
        await require_access(actor, record.enquiry_id, AccessAction.REVIEW, repo=_repo(record))

    async def test_unassigned_real_enquiry_is_not_found(self) -> None:
        actor = _actor(roles=["reviewer"])  # forged/claimed reviewer, assigned to someone else
        record = EnquiryAccess(uuid4(), None, None, None, uuid4())
        with self.assertRaises(PartsIQError) as ctx:
            await require_access(actor, record.enquiry_id, AccessAction.READ, repo=_repo(record))
        self.assertEqual(ctx.exception.http_status, 404)  # not 403 — existence not leaked

    async def test_assignment_is_admin_only(self) -> None:
        reviewer = _actor(roles=["reviewer"])
        record = EnquiryAccess(uuid4(), None, None, None, reviewer.user_id)
        with self.assertRaises(PartsIQError) as ctx:
            await require_access(
                reviewer, record.enquiry_id, AccessAction.ASSIGN, repo=_repo(record)
            )
        self.assertEqual(ctx.exception.code, "FORBIDDEN")
        self.assertEqual(ctx.exception.http_status, 403)

    async def test_admin_can_assign(self) -> None:
        admin = _actor(roles=["admin"])
        record = EnquiryAccess(uuid4(), None, None, None, None)
        await require_access(admin, record.enquiry_id, AccessAction.ASSIGN, repo=_repo(record))

    async def test_import_requires_catalogue_admin_or_admin(self) -> None:
        admin = _actor(roles=["admin"])
        record = EnquiryAccess(uuid4(), None, None, None, admin.user_id)
        await require_access(admin, record.enquiry_id, AccessAction.IMPORT, repo=_repo(record))

    async def test_missing_enquiry_is_not_found(self) -> None:
        async def repo(_):
            return None

        with self.assertRaises(PartsIQError) as ctx:
            await require_access(_actor(roles=["admin"]), uuid4(), AccessAction.READ, repo=repo)
        self.assertEqual(ctx.exception.code, "NOT_FOUND")


# --- demo sessions (F04 / F05) ----------------------------------------------


def _future():
    from datetime import timedelta

    return datetime.now(tz=timezone.utc) + timedelta(hours=24)


class DemoSessions(unittest.IsolatedAsyncioTestCase):
    async def test_rate_limit_runs_before_database(self) -> None:
        created = {"n": 0}

        class Store:
            async def create_session(self, owner_id):
                created["n"] += 1
                return DemoSession(id=uuid4(), generation=1, expires_at=_future())

            async def reset_session(self, owner_id, key):  # pragma: no cover
                raise AssertionError

        async def denied(_key):
            return False

        with self.assertRaises(PartsIQError) as ctx:
            await create_demo(_actor(), store=Store(), rate_limiter=denied)
        self.assertEqual(ctx.exception.code, "QUOTA_EXCEEDED")
        self.assertEqual(created["n"], 0)  # no DB write when rate limited

    async def test_create_demo_success(self) -> None:
        class Store:
            async def create_session(self, owner_id):
                return DemoSession(id=uuid4(), generation=1, expires_at=_future())

            async def reset_session(self, owner_id, key):  # pragma: no cover
                raise AssertionError

        async def allowed(_key):
            return True

        session = await create_demo(_actor(), store=Store(), rate_limiter=allowed)
        self.assertEqual(session.generation, 1)

    async def test_in_memory_store_honours_ttl_and_generation(self) -> None:
        settings = Settings(demo_session_ttl_seconds=3600)
        store = InMemoryDemoStore(settings)

        async def allowed(_key):
            return True

        actor = _actor()
        before = datetime.now(tz=timezone.utc)
        session = await create_demo(actor, store=store, rate_limiter=allowed)
        self.assertEqual(session.generation, 1)
        # Access expiry is TTL-driven (24h default here reduced to 1h for the assertion).
        delta = (session.expires_at - before).total_seconds()
        self.assertTrue(3500 <= delta <= 3700, delta)

    async def test_reset_bumps_generation_isolating_old_data(self) -> None:
        store = InMemoryDemoStore(Settings())
        actor = _actor()

        async def allowed(_key):
            return True

        created = await create_demo(actor, store=store, rate_limiter=allowed)
        reset = await reset_demo(actor, uuid4(), store=store)
        self.assertEqual(created.generation, 1)
        self.assertEqual(reset.generation, 2)  # old-generation data now isolated

    async def test_reset_is_idempotent_per_key(self) -> None:
        store = InMemoryDemoStore(Settings())
        actor = _actor()
        key = uuid4()
        first = await reset_demo(actor, key, store=store)
        again = await reset_demo(actor, key, store=store)
        self.assertEqual(first.generation, again.generation)  # same key -> same generation

    async def test_new_key_advances_generation(self) -> None:
        store = InMemoryDemoStore(Settings())
        actor = _actor()
        await reset_demo(actor, uuid4(), store=store)
        latest = await reset_demo(actor, uuid4(), store=store)
        self.assertEqual(latest.generation, 3)

    async def test_demo_requires_authenticated_identity(self) -> None:
        async def allowed(_key):  # pragma: no cover
            return True

        with self.assertRaises(PartsIQError) as ctx:
            await create_demo(None, store=InMemoryDemoStore(Settings()), rate_limiter=allowed)
        self.assertEqual(ctx.exception.code, "UNAUTHENTICATED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
