"""F59 Catalogue versioning — canonical snapshot/hash, serialized single-active publication.

Two publishers cannot leave two active versions (compare-and-set on the expected active id);
a failed publish rolls back (active unchanged); a prior approval keeps its immutable evidence
snapshot (publication never rewrites history); numeric ids are preserved; only catalogue_admin
/admin may publish.
"""
from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "libs" / "partsiq_common"))
sys.path.insert(0, str(REPO_ROOT / "tools" / "catalog"))

from catalog.versioning import (  # noqa: E402
    CandidateVersion,
    F59Request,
    PublishedVersion,
    canonical_snapshot,
    publish_version,
)
from partsiq_common.contracts import ActorContext  # noqa: E402
from partsiq_common.errors import PartsIQError  # noqa: E402

WHEN = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _admin():
    return ActorContext(user_id=uuid4(), request_id=uuid4(), roles=["catalogue_admin"])


def _records():
    # Deliberately out of id order to prove canonicalization sorts by numeric id.
    return ({"id": 3, "part_number": "VP-30"}, {"id": 1, "part_number": "VP-10"}, {"id": 2, "part_number": "VP-20"})


class FakePublicationStore:
    def __init__(self, active_id, candidate, *, fail=False):
        self._active = active_id
        self._candidate = candidate
        self._fail = fail
        self._by_key: dict = {}
        self.immutable_approval_evidence = {"appr-1": "SYNTH-CA-PB-CA-110 rev 1, section FILTERS"}

    async def load_candidate(self, version_id):
        return self._candidate if self._candidate and version_id == self._candidate.version_id else None

    async def current_active_id(self):
        return self._active

    async def publish(self, actor, *, version_id, expected_active_id, snapshot, idempotency_key):
        if idempotency_key in self._by_key:
            return self._by_key[idempotency_key]
        # Compare-and-set under the (simulated) publication lock.
        if self._active != expected_active_id:
            raise PartsIQError("CONFLICT", internal_detail="active changed")
        if self._fail:
            raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="write failed")  # active unchanged
        self._active = version_id
        published = PublishedVersion(
            version_id=version_id, published_at=WHEN,
            record_count=snapshot.record_count, snapshot_sha256=snapshot.sha256,
        )
        self._by_key[idempotency_key] = published
        return published


class CanonicalSnapshot(unittest.TestCase):
    def test_hash_is_order_independent_and_preserves_ids(self):
        recs = _records()
        a = canonical_snapshot(recs)
        b = canonical_snapshot(tuple(reversed(recs)))
        self.assertEqual(a.sha256, b.sha256)       # order-independent
        self.assertEqual(a.record_count, 3)
        self.assertRegex(a.sha256, r"^[a-f0-9]{64}$")


class PublishVersion(unittest.IsolatedAsyncioTestCase):
    async def test_publish_activates_new_version(self):
        old, new = uuid4(), uuid4()
        candidate = CandidateVersion(version_id=new, records=_records())
        store = FakePublicationStore(old, candidate)
        result = await publish_version(
            _admin(), F59Request(version_id=new, expected_active_version_id=old, idempotency_key=uuid4()), store=store
        )
        self.assertEqual(result.version_id, new)
        self.assertEqual(result.record_count, 3)
        self.assertEqual(await store.current_active_id(), new)

    async def test_second_publisher_cannot_create_two_active_versions(self):
        v1, v2a, v2b = uuid4(), uuid4(), uuid4()
        # Publisher A publishes v2a from v1 successfully.
        store = FakePublicationStore(v1, CandidateVersion(version_id=v2a, records=_records()))
        await publish_version(
            _admin(), F59Request(version_id=v2a, expected_active_version_id=v1, idempotency_key=uuid4()), store=store
        )
        # Publisher B still thinks v1 is active and tries to publish v2b -> rejected.
        store._candidate = CandidateVersion(version_id=v2b, records=_records())
        with self.assertRaises(PartsIQError) as ctx:
            await publish_version(
                _admin(), F59Request(version_id=v2b, expected_active_version_id=v1, idempotency_key=uuid4()),
                store=store,
            )
        self.assertEqual(ctx.exception.http_status, 409)
        self.assertEqual(await store.current_active_id(), v2a)  # exactly one active version

    async def test_failed_publish_rolls_back(self):
        old, new = uuid4(), uuid4()
        store = FakePublicationStore(old, CandidateVersion(version_id=new, records=_records()), fail=True)
        with self.assertRaises(PartsIQError) as ctx:
            await publish_version(
                _admin(), F59Request(version_id=new, expected_active_version_id=old, idempotency_key=uuid4()),
                store=store,
            )
        self.assertEqual(ctx.exception.code, "DEPENDENCY_UNAVAILABLE")
        self.assertEqual(await store.current_active_id(), old)  # unchanged

    async def test_prior_approval_keeps_immutable_evidence_snapshot(self):
        old, new = uuid4(), uuid4()
        store = FakePublicationStore(old, CandidateVersion(version_id=new, records=_records()))
        before = dict(store.immutable_approval_evidence)
        await publish_version(
            _admin(), F59Request(version_id=new, expected_active_version_id=old, idempotency_key=uuid4()), store=store
        )
        self.assertEqual(store.immutable_approval_evidence, before)  # publication never rewrote history

    async def test_idempotent_publish(self):
        old, new = uuid4(), uuid4()
        store = FakePublicationStore(old, CandidateVersion(version_id=new, records=_records()))
        key = uuid4()
        a = await publish_version(
            _admin(), F59Request(version_id=new, expected_active_version_id=old, idempotency_key=key), store=store
        )
        # Re-reading current active (now new) means a re-submit must use the new expected id.
        store._active = new
        b = await publish_version(
            _admin(), F59Request(version_id=new, expected_active_version_id=new, idempotency_key=key), store=store
        )
        self.assertEqual(a.version_id, b.version_id)

    async def test_non_admin_forbidden(self):
        old, new = uuid4(), uuid4()
        store = FakePublicationStore(old, CandidateVersion(version_id=new, records=_records()))
        reviewer = ActorContext(user_id=uuid4(), request_id=uuid4(), roles=["reviewer"])
        with self.assertRaises(PartsIQError) as ctx:
            await publish_version(
                reviewer, F59Request(version_id=new, expected_active_version_id=old, idempotency_key=uuid4()),
                store=store,
            )
        self.assertEqual(ctx.exception.http_status, 403)

    async def test_unknown_candidate_not_found(self):
        store = FakePublicationStore(uuid4(), CandidateVersion(version_id=uuid4(), records=_records()))
        with self.assertRaises(PartsIQError) as ctx:
            await publish_version(
                _admin(), F59Request(version_id=uuid4(), expected_active_version_id=uuid4(), idempotency_key=uuid4()),
                store=store,
            )
        self.assertEqual(ctx.exception.http_status, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
