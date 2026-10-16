"""F04 Demo isolation — each session bound to its verified anonymous identity.

Expired/reset (generation mismatch), foreign and missing-context sessions all fail; only the
owner of the active session may read/review its demo enquiry. Exercises the existing
require_access decision with an injected access record (no DB needed offline).
"""
from __future__ import annotations

import unittest
from uuid import uuid4

from app.permissions import EnquiryAccess, require_access
from partsiq_common.contracts import AccessAction, ActorContext
from partsiq_common.errors import PartsIQError


def _repo(record):
    async def fetch(_enquiry_id):
        return record

    return fetch


def _demo_record(owner, session, generation):
    return EnquiryAccess(enquiry_id=uuid4(), owner_id=owner, session_id=session, session_generation=generation, assigned_to=None)


def _actor(user_id, session, generation):
    return ActorContext(user_id=user_id, request_id=uuid4(), roles=[], session_id=session, session_generation=generation)


class DemoIsolation(unittest.IsolatedAsyncioTestCase):
    async def test_owner_of_active_session_allowed(self):
        owner, session = uuid4(), uuid4()
        rec = _demo_record(owner, session, 2)
        await require_access(_actor(owner, session, 2), rec.enquiry_id, AccessAction.READ, repo=_repo(rec))

    async def test_expired_or_reset_generation_fails(self):
        owner, session = uuid4(), uuid4()
        rec = _demo_record(owner, session, 3)                       # current generation 3
        with self.assertRaises(PartsIQError) as ctx:
            await require_access(_actor(owner, session, 2), rec.enquiry_id, AccessAction.READ, repo=_repo(rec))
        self.assertEqual(ctx.exception.http_status, 404)

    async def test_foreign_session_fails(self):
        owner, session = uuid4(), uuid4()
        rec = _demo_record(owner, session, 1)
        with self.assertRaises(PartsIQError):
            await require_access(_actor(uuid4(), uuid4(), 1), rec.enquiry_id, AccessAction.READ, repo=_repo(rec))

    async def test_missing_context_returns_no_rows(self):
        with self.assertRaises(PartsIQError) as ctx:
            await require_access(_actor(uuid4(), uuid4(), 1), uuid4(), AccessAction.READ, repo=_repo(None))
        self.assertEqual(ctx.exception.http_status, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
