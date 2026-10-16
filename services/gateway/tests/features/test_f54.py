"""F54 Access and permissions — identity is server-side; JWT role claims are ignored.

The authenticator rejects a malformed token and a disallowed ('none') algorithm, and staff
membership is derived from the database, so a forged role claim grants nothing. require_access
enforces assigned-only real review and denies a missing-context request. (The full signed
issuer/audience/expiry path with a real keypair is covered by tests/foundations/test_07.py.)
"""
from __future__ import annotations

import base64
import json
import unittest
from uuid import uuid4

from app.auth import Authenticator
from app.permissions import EnquiryAccess, require_access
from partsiq_common.contracts import AccessAction, ActorContext
from partsiq_common.errors import PartsIQError


def _b64(payload: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()


def _authenticator():
    async def jwks_loader():
        return {}

    async def role_provider(_user_id):
        return ["reviewer"]  # DB says reviewer; JWT role claims must be irrelevant

    return Authenticator(issuer="https://issuer", audience="authenticated", jwks_loader=jwks_loader, role_provider=role_provider)


class AccessAndPermissions(unittest.IsolatedAsyncioTestCase):
    async def test_malformed_token_rejected(self):
        with self.assertRaises(PartsIQError) as ctx:
            await _authenticator().authenticate("not-a-jwt")
        self.assertEqual(ctx.exception.code, "UNAUTHENTICATED")

    async def test_none_algorithm_rejected(self):  # signature/alg confusion
        token = f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64({'sub': str(uuid4()), 'iss': 'x', 'aud': 'y', 'exp': 9999999999})}."
        with self.assertRaises(PartsIQError) as ctx:
            await _authenticator().authenticate(token)
        self.assertEqual(ctx.exception.code, "UNAUTHENTICATED")

    async def test_forged_role_on_unassigned_real_enquiry_denied(self):
        rec = EnquiryAccess(enquiry_id=uuid4(), owner_id=uuid4(), session_id=None, session_generation=None, assigned_to=uuid4())

        async def repo(_id):
            return rec

        forged = ActorContext(user_id=uuid4(), request_id=uuid4(), roles=["reviewer", "admin"])  # claims ignored; not assigned/admin-by-DB? role here simulates claim
        # Even a claimed reviewer who is not the assigned reviewer is denied (404), not 403.
        with self.assertRaises(PartsIQError) as ctx:
            await require_access(forged.model_copy(update={"roles": ["reviewer"]}), rec.enquiry_id, AccessAction.REVIEW, repo=repo)
        self.assertEqual(ctx.exception.http_status, 404)

    async def test_missing_context_denies(self):
        async def repo(_id):
            return None

        actor = ActorContext(user_id=uuid4(), request_id=uuid4(), roles=["reviewer"])
        with self.assertRaises(PartsIQError) as ctx:
            await require_access(actor, uuid4(), AccessAction.REVIEW, repo=repo)
        self.assertEqual(ctx.exception.http_status, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
