"""F42 Assignments — admin assigns/unassigns an active reviewer; access changes immediately.

Non-admin denied (403); a disabled/non-reviewer assignee rejected (422); a stale revision is
409; the write is idempotent; a reassignment moves access off the previous reviewer.
"""
from __future__ import annotations

import unittest
from datetime import UTC, datetime
from uuid import uuid4

from app.features.f42_assignments import (
    AssignmentRecord,
    AssignmentState,
    F42Request,
    assign_enquiry,
)
from partsiq_common.contracts import ActorContext
from partsiq_common.errors import PartsIQError

WHEN = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _admin():
    return ActorContext(user_id=uuid4(), request_id=uuid4(), roles=["admin"])


def _reviewer():
    return ActorContext(user_id=uuid4(), request_id=uuid4(), roles=["reviewer"])


class FakeAssignmentRepo:
    def __init__(self, revision=1, active_reviewers=(), *, missing=False, raises=None):
        self._revision = revision
        self._active = set(active_reviewers)
        self._missing = missing
        self._raises = raises
        self.assigned_to = None
        self._by_key: dict = {}

    async def load_assignment_state(self, enquiry_id):
        if self._raises is not None:
            raise self._raises
        if self._missing:
            return None
        return AssignmentState(revision=self._revision, assigned_to=self.assigned_to)

    async def is_active_reviewer(self, user_id):
        return user_id in self._active

    async def apply_assignment(self, actor, enquiry_id, assigned_to, idempotency_key):
        if idempotency_key in self._by_key:
            return self._by_key[idempotency_key]
        self.assigned_to = assigned_to  # atomic swap -> access changes immediately
        record = AssignmentRecord(assigned_to=assigned_to, assigned_at=WHEN)
        self._by_key[idempotency_key] = record
        return record


def _req(assigned_to, revision=1, key=None):
    return F42Request(enquiry_id=uuid4(), assigned_to=assigned_to, expected_revision=revision,
                      idempotency_key=key or uuid4())


class AssignEnquiry(unittest.IsolatedAsyncioTestCase):
    async def test_admin_assigns_active_reviewer(self):
        reviewer = uuid4()
        repo = FakeAssignmentRepo(active_reviewers={reviewer})
        result = await assign_enquiry(_admin(), _req(reviewer), repo=repo)
        self.assertEqual(result.assigned_to, reviewer)
        self.assertEqual(result.assigned_at, WHEN)

    async def test_admin_unassigns(self):
        repo = FakeAssignmentRepo()
        result = await assign_enquiry(_admin(), _req(None), repo=repo)
        self.assertIsNone(result.assigned_to)

    async def test_non_admin_denied(self):
        reviewer = uuid4()
        repo = FakeAssignmentRepo(active_reviewers={reviewer})
        with self.assertRaises(PartsIQError) as ctx:
            await assign_enquiry(_reviewer(), _req(reviewer), repo=repo)
        self.assertEqual(ctx.exception.http_status, 403)

    async def test_disabled_or_nonreviewer_assignee_rejected(self):
        repo = FakeAssignmentRepo(active_reviewers=set())  # target is not an active reviewer
        with self.assertRaises(PartsIQError) as ctx:
            await assign_enquiry(_admin(), _req(uuid4()), repo=repo)
        self.assertEqual(ctx.exception.http_status, 422)

    async def test_stale_revision_rejected(self):
        reviewer = uuid4()
        repo = FakeAssignmentRepo(revision=3, active_reviewers={reviewer})
        with self.assertRaises(PartsIQError) as ctx:
            await assign_enquiry(_admin(), _req(reviewer, revision=1), repo=repo)
        self.assertEqual(ctx.exception.http_status, 409)

    async def test_idempotent_assignment(self):
        reviewer = uuid4()
        repo = FakeAssignmentRepo(active_reviewers={reviewer})
        key = uuid4()
        a = await assign_enquiry(_admin(), _req(reviewer, key=key), repo=repo)
        b = await assign_enquiry(_admin(), _req(reviewer, key=key), repo=repo)
        self.assertEqual(a.assigned_at, b.assigned_at)

    async def test_reassignment_moves_access_off_previous_reviewer(self):
        first, second = uuid4(), uuid4()
        repo = FakeAssignmentRepo(active_reviewers={first, second})
        await assign_enquiry(_admin(), _req(first), repo=repo)
        await assign_enquiry(_admin(), _req(second), repo=repo)
        self.assertEqual(repo.assigned_to, second)  # previous reviewer no longer assigned

    async def test_missing_enquiry_not_found(self):
        repo = FakeAssignmentRepo(missing=True)
        with self.assertRaises(PartsIQError) as ctx:
            await assign_enquiry(_admin(), _req(None), repo=repo)
        self.assertEqual(ctx.exception.http_status, 404)

    async def test_dependency_failure_propagates(self):
        repo = FakeAssignmentRepo(raises=PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="down"))
        with self.assertRaises(PartsIQError) as ctx:
            await assign_enquiry(_admin(), _req(None), repo=repo)
        self.assertEqual(ctx.exception.code, "DEPENDENCY_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
