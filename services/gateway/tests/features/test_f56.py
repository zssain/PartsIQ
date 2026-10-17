"""F56 Repeat enquiry — copy request + confirmed hints only; fresh id/revision; audit origin.

Never copies approval/allocation/draft/signed URL (structurally impossible — RepeatSpec has no
such field); source ownership is required (foreign -> NOT_FOUND); a repeated submission with
the same key is deduplicated.
"""
from __future__ import annotations

import dataclasses
import unittest
from datetime import UTC, datetime
from uuid import uuid4

from app.features.f56_repeat_enquiry import (
    ConfirmedHint,
    F56Request,
    RepeatSource,
    RepeatSpec,
    repeat_enquiry,
)
from partsiq_common.contracts import ActorContext, EnquiryView
from partsiq_common.errors import PartsIQError

WHEN = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _actor(user_id=None):
    return ActorContext(user_id=user_id or uuid4(), request_id=uuid4(), roles=["reviewer"])


def _source(enquiry_id=None):
    return RepeatSource(
        enquiry_id=enquiry_id or uuid4(),
        text="I need a fuel filter for my loader",
        locale="en",
        destination_warehouse_id=1,
        confirmed_hints=(ConfirmedHint(description="fuel filter", model_text="VP-20", serial_text="000150"),),
        approval_id=uuid4(),          # outcome fields that must NOT be copied
        draft_id=uuid4(),
        allocations=((1, 2),),
        signed_file_urls=("https://signed/evidence.pdf",),
    )


class FakeRepeatRepo:
    def __init__(self, source, owner):
        self._source = source
        self._owner = owner
        self._by_key: dict = {}
        self.specs: list[RepeatSpec] = []
        self.audited_origin: list = []
        self.enqueued_start = 0

    async def load_source(self, actor, source_enquiry_id):
        if actor.user_id != self._owner or source_enquiry_id != self._source.enquiry_id:
            return None
        return self._source

    async def create_repeat(self, actor, spec, idempotency_key):
        key = (actor.user_id, idempotency_key)
        if key in self._by_key:
            return self._by_key[key]  # dedupe
        self.specs.append(spec)
        self.audited_origin.append(spec.source_enquiry_id)
        self.enqueued_start += 1  # pipeline runs again
        view = EnquiryView(
            id=uuid4(), revision=1, status="received", messages=[], item_ids=[],
            catalogue_version_id=None, updated_at=WHEN,
        )
        self._by_key[key] = view
        return view


class Failing:
    async def load_source(self, *a, **k):
        raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="db down")


class RepeatEnquiry(unittest.IsolatedAsyncioTestCase):
    async def test_copies_request_into_fresh_enquiry(self):
        owner = _actor()
        source = _source()
        repo = FakeRepeatRepo(source, owner.user_id)
        result = await repeat_enquiry(
            owner, F56Request(source_enquiry_id=source.enquiry_id, idempotency_key=uuid4()), repo=repo
        )
        self.assertNotEqual(result.enquiry.id, source.enquiry_id)  # new id
        self.assertEqual(result.enquiry.revision, 1)               # fresh revision
        self.assertEqual(repo.enqueued_start, 1)                   # pipeline re-runs
        self.assertEqual(repo.audited_origin, [source.enquiry_id]) # origin linked in audit
        spec = repo.specs[0]
        self.assertEqual(spec.text, source.text)
        self.assertEqual(spec.confirmed_hints[0].serial_text, "000150")

    async def test_never_copies_outcome_fields(self):
        spec_fields = {f.name for f in dataclasses.fields(RepeatSpec)}
        for forbidden in ("approval_id", "draft_id", "allocations", "signed_file_urls"):
            self.assertNotIn(forbidden, spec_fields)

    async def test_source_ownership_required(self):
        owner, stranger = _actor(), _actor()
        source = _source()
        repo = FakeRepeatRepo(source, owner.user_id)
        with self.assertRaises(PartsIQError) as ctx:
            await repeat_enquiry(
                stranger, F56Request(source_enquiry_id=source.enquiry_id, idempotency_key=uuid4()), repo=repo
            )
        self.assertEqual(ctx.exception.http_status, 404)

    async def test_repeated_submission_deduplicated(self):
        owner = _actor()
        source = _source()
        repo = FakeRepeatRepo(source, owner.user_id)
        key = uuid4()
        a = await repeat_enquiry(owner, F56Request(source_enquiry_id=source.enquiry_id, idempotency_key=key), repo=repo)
        b = await repeat_enquiry(owner, F56Request(source_enquiry_id=source.enquiry_id, idempotency_key=key), repo=repo)
        self.assertEqual(a.enquiry.id, b.enquiry.id)
        self.assertEqual(repo.enqueued_start, 1)  # not re-run on the duplicate

    async def test_dependency_failure_propagates(self):
        with self.assertRaises(PartsIQError) as ctx:
            await repeat_enquiry(
                _actor(), F56Request(source_enquiry_id=uuid4(), idempotency_key=uuid4()), repo=Failing()
            )
        self.assertEqual(ctx.exception.code, "DEPENDENCY_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
