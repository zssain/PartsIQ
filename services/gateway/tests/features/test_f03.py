"""F03 Demo role switching — same anonymous session reviews its own demo enquiries only.

A forged reviewer role never grants access to a real enquiry that is not assigned; another
visitor's (or a stale-generation) demo enquiry returns 404, so existence is never leaked.
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


def _demo_actor(session_id, generation, user_id):
    return ActorContext(user_id=user_id, request_id=uuid4(), roles=[], session_id=session_id, session_generation=generation)


class DemoRoleSwitching(unittest.IsolatedAsyncioTestCase):
    async def test_own_active_session_may_review_demo(self):  # success
        session, user = uuid4(), uuid4()
        record = EnquiryAccess(enquiry_id=uuid4(), owner_id=user, session_id=session, session_generation=2, assigned_to=None)
        await require_access(_demo_actor(session, 2, user), record.enquiry_id, AccessAction.REVIEW, repo=_repo(record))

    async def test_other_visitor_demo_enquiry_is_404(self):  # unauthorized
        owner_session, owner = uuid4(), uuid4()
        record = EnquiryAccess(enquiry_id=uuid4(), owner_id=owner, session_id=owner_session, session_generation=1, assigned_to=None)
        stranger = _demo_actor(uuid4(), 1, uuid4())
        with self.assertRaises(PartsIQError) as ctx:
            await require_access(stranger, record.enquiry_id, AccessAction.REVIEW, repo=_repo(record))
        self.assertEqual(ctx.exception.http_status, 404)

    async def test_stale_generation_is_404(self):  # stale-revision/generation
        session, user = uuid4(), uuid4()
        record = EnquiryAccess(enquiry_id=uuid4(), owner_id=user, session_id=session, session_generation=3, assigned_to=None)
        with self.assertRaises(PartsIQError):
            await require_access(_demo_actor(session, 2, user), record.enquiry_id, AccessAction.REVIEW, repo=_repo(record))

    async def test_forged_reviewer_role_on_unassigned_real_enquiry_is_404(self):
        # A real (non-demo) enquiry not assigned to the actor: a claimed reviewer role is ignored.
        record = EnquiryAccess(enquiry_id=uuid4(), owner_id=uuid4(), session_id=None, session_generation=None, assigned_to=uuid4())
        forged = ActorContext(user_id=uuid4(), request_id=uuid4(), roles=["reviewer"])
        with self.assertRaises(PartsIQError) as ctx:
            await require_access(forged, record.enquiry_id, AccessAction.REVIEW, repo=_repo(record))
        self.assertEqual(ctx.exception.http_status, 404)

    async def test_assigned_reviewer_may_review_real(self):
        reviewer = uuid4()
        record = EnquiryAccess(enquiry_id=uuid4(), owner_id=uuid4(), session_id=None, session_generation=None, assigned_to=reviewer)
        actor = ActorContext(user_id=reviewer, request_id=uuid4(), roles=["reviewer"])
        await require_access(actor, record.enquiry_id, AccessAction.REVIEW, repo=_repo(record))

    async def test_missing_enquiry_is_404(self):  # dependency/invalid
        actor = ActorContext(user_id=uuid4(), request_id=uuid4(), roles=["reviewer"])
        with self.assertRaises(PartsIQError) as ctx:
            await require_access(actor, uuid4(), AccessAction.REVIEW, repo=_repo(None))
        self.assertEqual(ctx.exception.http_status, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
