"""F29 Evidence page viewer — authorize + short-lived signed PDF to the exact cited page.

Assigned reviewer or own demo reviewer only (customers denied); a typed evidence id that does
not resolve is rejected (no arbitrary Storage key); every document is labelled synthetic; an
expired link is renewed by calling again; a stale revision is 409.
"""
from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.features.f29_evidence_page_viewer import (
    EvidenceRef,
    F29Request,
    ReviewAccess,
    SignedDoc,
    open_evidence,
)
from partsiq_common.contracts import ActorContext
from partsiq_common.errors import PartsIQError

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _actor(user_id=None, session_id=None, generation=None):
    return ActorContext(user_id=user_id or uuid4(), request_id=uuid4(), roles=["reviewer"],
                        session_id=session_id, session_generation=generation)


class FakeEvidenceStore:
    def __init__(self, access, *, known_evidence=None, raises=None):
        self._access = access
        self._known = set(known_evidence or [])
        self._raises = raises
        self.sign_calls = 0

    async def load_access(self, actor, enquiry_id):
        if self._raises is not None:
            raise self._raises
        return self._access

    async def resolve_evidence(self, enquiry_id, evidence_id, revision):
        if evidence_id not in self._known:
            return None  # arbitrary / unknown id -> rejected
        return EvidenceRef(document="SYNTH-CA rev 1", page_number=7, storage_resource_id=uuid4())

    async def sign_pdf(self, evidence_ref):
        self.sign_calls += 1
        return SignedDoc(url=f"https://signed/{self.sign_calls}", expires_at=NOW + timedelta(seconds=60))


def _assigned_access(reviewer_id, revision=1):
    return ReviewAccess(revision=revision, assigned_to=reviewer_id, is_demo=False,
                        session_id=None, session_generation=None)


class OpenEvidence(unittest.IsolatedAsyncioTestCase):
    async def test_assigned_reviewer_opens_cited_page(self):
        reviewer = _actor()
        evidence = uuid4()
        store = FakeEvidenceStore(_assigned_access(reviewer.user_id), known_evidence={evidence})
        result = await open_evidence(
            reviewer, F29Request(enquiry_id=uuid4(), evidence_id=evidence, expected_revision=1), store=store
        )
        self.assertEqual(result.page_number, 7)
        self.assertTrue(result.synthetic)
        self.assertTrue(result.url.startswith("https://signed/"))
        self.assertGreater(result.expires_at, NOW)

    async def test_own_demo_reviewer_opens(self):
        session, generation = uuid4(), 3
        reviewer = _actor(session_id=session, generation=generation)
        evidence = uuid4()
        access = ReviewAccess(revision=1, assigned_to=None, is_demo=True, session_id=session, session_generation=generation)
        store = FakeEvidenceStore(access, known_evidence={evidence})
        result = await open_evidence(
            reviewer, F29Request(enquiry_id=uuid4(), evidence_id=evidence, expected_revision=1), store=store
        )
        self.assertTrue(result.synthetic)

    async def test_customer_denied_reference_only(self):
        evidence = uuid4()
        # The enquiry is assigned to someone else; a non-assigned actor gets NOT_FOUND (no URL).
        store = FakeEvidenceStore(_assigned_access(uuid4()), known_evidence={evidence})
        with self.assertRaises(PartsIQError) as ctx:
            await open_evidence(
                _actor(), F29Request(enquiry_id=uuid4(), evidence_id=evidence, expected_revision=1), store=store
            )
        self.assertEqual(ctx.exception.http_status, 404)

    async def test_demo_session_mismatch_denied(self):
        access = ReviewAccess(revision=1, assigned_to=None, is_demo=True, session_id=uuid4(), session_generation=1)
        store = FakeEvidenceStore(access, known_evidence={uuid4()})
        with self.assertRaises(PartsIQError) as ctx:
            await open_evidence(
                _actor(session_id=uuid4(), generation=1),
                F29Request(enquiry_id=uuid4(), evidence_id=uuid4(), expected_revision=1), store=store
            )
        self.assertEqual(ctx.exception.http_status, 404)

    async def test_arbitrary_evidence_id_rejected(self):
        reviewer = _actor()
        store = FakeEvidenceStore(_assigned_access(reviewer.user_id), known_evidence=set())
        with self.assertRaises(PartsIQError) as ctx:
            await open_evidence(
                reviewer, F29Request(enquiry_id=uuid4(), evidence_id=uuid4(), expected_revision=1), store=store
            )
        self.assertEqual(ctx.exception.http_status, 404)

    async def test_stale_revision_rejected(self):
        reviewer = _actor()
        evidence = uuid4()
        store = FakeEvidenceStore(_assigned_access(reviewer.user_id, revision=3), known_evidence={evidence})
        with self.assertRaises(PartsIQError) as ctx:
            await open_evidence(
                reviewer, F29Request(enquiry_id=uuid4(), evidence_id=evidence, expected_revision=1), store=store
            )
        self.assertEqual(ctx.exception.http_status, 409)

    async def test_expired_link_renewed_on_reopen(self):
        reviewer = _actor()
        evidence = uuid4()
        store = FakeEvidenceStore(_assigned_access(reviewer.user_id), known_evidence={evidence})
        req = F29Request(enquiry_id=uuid4(), evidence_id=evidence, expected_revision=1)
        first = await open_evidence(reviewer, req, store=store)
        second = await open_evidence(reviewer, req, store=store)
        self.assertNotEqual(first.url, second.url)  # a fresh signed URL each time
        self.assertEqual(store.sign_calls, 2)

    async def test_dependency_failure_propagates(self):
        store = FakeEvidenceStore(None, raises=PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="down"))
        with self.assertRaises(PartsIQError) as ctx:
            await open_evidence(
                _actor(), F29Request(enquiry_id=uuid4(), evidence_id=uuid4(), expected_revision=1), store=store
            )
        self.assertEqual(ctx.exception.code, "DEPENDENCY_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
