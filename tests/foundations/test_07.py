"""Acceptance tests for prompt 07 — authentication and demo sessions.

Fully offline: a throwaway RSA keypair backs a local JWKS, so Supabase JWT verification
(issuer/audience/expiry/algorithm, unknown-kid refresh, DB-sourced roles) is exercised
with real signatures. Permissions and demo flows run against in-memory fakes. Live
Supabase Auth and DB persistence are integration-only and reported BLOCKED.

Covers F03, F04, F05, F54.
"""
from __future__ import annotations

import json
import sys
import time
import unittest
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "partsiq_common"))
sys.path.insert(0, str(REPO_ROOT / "services" / "gateway"))

import jwt  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from jwt.algorithms import RSAAlgorithm  # noqa: E402

from app.auth import Authenticator, jwks_from_keyset  # noqa: E402
from app.demo import create_demo, reset_demo  # noqa: E402
from app.permissions import EnquiryAccess, require_access  # noqa: E402
from partsiq_common.contracts import AccessAction, ActorContext, DemoSession  # noqa: E402
from partsiq_common.errors import PartsIQError  # noqa: E402

ISS = "https://proj.supabase.co/auth/v1"
AUD = "authenticated"
KID = "test-kid"
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


def authenticator(roles=None, loader=None):
    async def role_provider(_uid):
        return list(roles or [])

    async def default_loader():
        return _JWKS

    return Authenticator(
        issuer=ISS, audience=AUD, jwks_loader=loader or default_loader, role_provider=role_provider
    )


class JwtVerification(unittest.IsolatedAsyncioTestCase):
    async def test_valid_token_authenticates(self) -> None:
        uid = str(uuid4())
        actor = await authenticator().authenticate(make_token(uid))
        self.assertEqual(str(actor.user_id), uid)

    async def test_expired_token_rejected(self) -> None:
        with self.assertRaises(PartsIQError):
            await authenticator().authenticate(make_token(str(uuid4()), exp_delta=-10))

    async def test_wrong_issuer_rejected(self) -> None:
        with self.assertRaises(PartsIQError):
            await authenticator().authenticate(make_token(str(uuid4()), iss="https://evil/auth"))

    async def test_wrong_audience_rejected(self) -> None:
        with self.assertRaises(PartsIQError):
            await authenticator().authenticate(make_token(str(uuid4()), aud="other"))

    async def test_disallowed_algorithm_rejected(self) -> None:
        with self.assertRaises(PartsIQError):
            await authenticator().authenticate(make_token(str(uuid4()), alg="none"))

    async def test_forged_role_claim_is_ignored(self) -> None:
        # DB role provider returns nothing, so a forged 'role'/'roles' claim grants nothing.
        actor = await authenticator(roles=[]).authenticate(
            make_token(str(uuid4()), extra={"role": "admin", "roles": ["admin"]})
        )
        self.assertEqual(actor.roles, [])

    async def test_roles_come_from_database(self) -> None:
        actor = await authenticator(roles=["reviewer"]).authenticate(make_token(str(uuid4())))
        self.assertEqual(actor.roles, ["reviewer"])

    async def test_unknown_kid_refreshes_once_then_fails(self) -> None:
        calls = {"n": 0}

        async def loader():
            calls["n"] += 1
            return _JWKS  # never contains the 'ghost' kid

        with self.assertRaises(PartsIQError):
            await authenticator(loader=loader).authenticate(make_token(str(uuid4()), kid="ghost"))
        self.assertEqual(calls["n"], 1)  # refreshed exactly once


def _actor(roles=(), session_id=None, generation=None):
    return ActorContext(
        user_id=uuid4(), request_id=uuid4(), roles=list(roles),
        session_id=session_id, session_generation=generation,
    )


class AccessControl(unittest.IsolatedAsyncioTestCase):
    def _repo(self, record):
        async def repo(_enquiry_id):
            return record
        return repo

    async def test_own_active_demo_allowed(self) -> None:
        sid = uuid4()
        actor = _actor(session_id=sid, generation=2)
        record = EnquiryAccess(uuid4(), actor.user_id, sid, 2, None)
        await require_access(actor, record.enquiry_id, AccessAction.REVIEW, repo=self._repo(record))

    async def test_foreign_demo_is_not_found(self) -> None:
        actor = _actor(session_id=uuid4(), generation=1)
        record = EnquiryAccess(uuid4(), uuid4(), uuid4(), 1, None)  # different owner/session
        with self.assertRaises(PartsIQError) as ctx:
            await require_access(actor, record.enquiry_id, AccessAction.READ, repo=self._repo(record))
        self.assertEqual(ctx.exception.code, "NOT_FOUND")

    async def test_assigned_reviewer_can_review_real_enquiry(self) -> None:
        actor = _actor(roles=["reviewer"])
        record = EnquiryAccess(uuid4(), None, None, None, actor.user_id)
        await require_access(actor, record.enquiry_id, AccessAction.REVIEW, repo=self._repo(record))

    async def test_unassigned_real_enquiry_is_not_found(self) -> None:
        actor = _actor(roles=["reviewer"])
        record = EnquiryAccess(uuid4(), None, None, None, uuid4())  # assigned to someone else
        with self.assertRaises(PartsIQError) as ctx:
            await require_access(actor, record.enquiry_id, AccessAction.READ, repo=self._repo(record))
        self.assertEqual(ctx.exception.code, "NOT_FOUND")

    async def test_assignment_is_admin_only(self) -> None:
        reviewer = _actor(roles=["reviewer"])
        record = EnquiryAccess(uuid4(), None, None, None, reviewer.user_id)
        with self.assertRaises(PartsIQError) as ctx:
            await require_access(reviewer, record.enquiry_id, AccessAction.ASSIGN, repo=self._repo(record))
        self.assertEqual(ctx.exception.code, "FORBIDDEN")

    async def test_admin_can_assign(self) -> None:
        admin = _actor(roles=["admin"])
        record = EnquiryAccess(uuid4(), None, None, None, None)
        await require_access(admin, record.enquiry_id, AccessAction.ASSIGN, repo=self._repo(record))

    async def test_missing_enquiry_is_not_found(self) -> None:
        async def repo(_):
            return None
        with self.assertRaises(PartsIQError) as ctx:
            await require_access(_actor(roles=["admin"]), uuid4(), AccessAction.READ, repo=repo)
        self.assertEqual(ctx.exception.code, "NOT_FOUND")


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

    async def test_reset_is_idempotent_per_key(self) -> None:
        class Store:
            def __init__(self):
                self.by_key = {}
                self.generation = 1

            async def create_session(self, owner_id):  # pragma: no cover
                raise AssertionError

            async def reset_session(self, owner_id, key):
                if key not in self.by_key:
                    self.generation += 1
                    self.by_key[key] = DemoSession(id=uuid4(), generation=self.generation, expires_at=_future())
                return self.by_key[key]

        store = Store()
        actor = _actor()
        key = uuid4()
        first = await reset_demo(actor, key, store=store)
        again = await reset_demo(actor, key, store=store)
        self.assertEqual(first.generation, again.generation)  # same key -> same generation


def _future():
    from datetime import datetime, timedelta, timezone
    return datetime.now(tz=timezone.utc) + timedelta(hours=24)


if __name__ == "__main__":
    unittest.main(verbosity=2)
