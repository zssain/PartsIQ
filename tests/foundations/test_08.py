"""Acceptance tests for prompt 08 — enquiry intake and limits.

Offline: the intake use cases run against in-memory fakes, so idempotency (same key +
same payload returns the existing resource; different payload = 409), stale-revision
rejection, rate-limit-before-database ordering, and attachment confirmation (magic
check, duplicate idempotency, nonexistent) are all exercised without a DB or Storage.
Covers F13.
"""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "partsiq_common"))
sys.path.insert(0, str(REPO_ROOT / "services" / "gateway"))

from app.enquiries import IdempotentEnquiry, IdempotentMessage, add_message, canonical_hash, create_enquiry  # noqa: E402
from app.uploads import PendingAttachment, confirm_upload  # noqa: E402
from partsiq_common.contracts import (  # noqa: E402
    ActorContext,
    AttachmentView,
    EnquiryCreate,
    EnquiryView,
    MessageCreate,
    MessageView,
)
from partsiq_common.errors import PartsIQError  # noqa: E402

NOW = datetime(2026, 10, 17, tzinfo=timezone.utc)
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF"


def actor():
    return ActorContext(user_id=uuid4(), request_id=uuid4(), roles=[])


def an_enquiry_view(revision=1):
    return EnquiryView(
        id=uuid4(), revision=revision, status="received", messages=[], item_ids=[],
        catalogue_version_id=None, updated_at=NOW,
    )


def a_message_view(enquiry_id, revision=1):
    return MessageView(id=uuid4(), enquiry_id=enquiry_id, revision=revision, kind="customer", body="hi", created_at=NOW)


async def _allow(_key):
    return True


async def _deny(_key):
    return False


class FakeEnquiryRepo:
    def __init__(self, *, existing_enquiry=None, existing_message=None, current=1):
        self.existing_enquiry = existing_enquiry
        self.existing_message = existing_message
        self.current = current
        self.created = 0
        self.messages_added = 0

    async def get_enquiry_idempotent(self, actor, key):
        return self.existing_enquiry

    async def create_enquiry_atomic(self, actor, body, key, payload_hash):
        self.created += 1
        return an_enquiry_view()

    async def get_message_idempotent(self, actor, key):
        return self.existing_message

    async def current_revision(self, actor, enquiry_id):
        return self.current

    async def add_message_atomic(self, actor, enquiry_id, body, key, payload_hash):
        self.messages_added += 1
        return a_message_view(enquiry_id, self.current)


class CreateEnquiry(unittest.IsolatedAsyncioTestCase):
    def _body(self, text="need a filter"):
        return EnquiryCreate(text=text, locale="en", destination_warehouse_id=1)

    async def test_rate_limit_before_database(self) -> None:
        repo = FakeEnquiryRepo()
        with self.assertRaises(PartsIQError) as ctx:
            await create_enquiry(actor(), self._body(), uuid4(), repo=repo, rate_limiter=_deny)
        self.assertEqual(ctx.exception.code, "QUOTA_EXCEEDED")
        self.assertEqual(repo.created, 0)

    async def test_fresh_create_commits_once(self) -> None:
        repo = FakeEnquiryRepo()
        await create_enquiry(actor(), self._body(), uuid4(), repo=repo, rate_limiter=_allow)
        self.assertEqual(repo.created, 1)

    async def test_same_key_same_payload_returns_existing(self) -> None:
        body = self._body()
        existing = IdempotentEnquiry(payload_hash=canonical_hash(body), view=an_enquiry_view())
        repo = FakeEnquiryRepo(existing_enquiry=existing)
        view = await create_enquiry(actor(), body, uuid4(), repo=repo, rate_limiter=_allow)
        self.assertEqual(view.id, existing.view.id)
        self.assertEqual(repo.created, 0)

    async def test_same_key_different_payload_is_409(self) -> None:
        existing = IdempotentEnquiry(payload_hash=canonical_hash(self._body("A")), view=an_enquiry_view())
        repo = FakeEnquiryRepo(existing_enquiry=existing)
        with self.assertRaises(PartsIQError) as ctx:
            await create_enquiry(actor(), self._body("B"), uuid4(), repo=repo, rate_limiter=_allow)
        self.assertEqual(ctx.exception.code, "IDEMPOTENCY_MISMATCH")


class AddMessage(unittest.IsolatedAsyncioTestCase):
    def _body(self, revision=1):
        return MessageCreate(text="more info", expected_revision=revision)

    async def test_stale_revision_rejected(self) -> None:
        repo = FakeEnquiryRepo(current=2)
        with self.assertRaises(PartsIQError) as ctx:
            await add_message(actor(), uuid4(), self._body(revision=1), uuid4(), repo=repo)
        self.assertEqual(ctx.exception.code, "STALE_REVISION")

    async def test_current_revision_accepted(self) -> None:
        repo = FakeEnquiryRepo(current=1)
        await add_message(actor(), uuid4(), self._body(revision=1), uuid4(), repo=repo)
        self.assertEqual(repo.messages_added, 1)

    async def test_nonexistent_enquiry_is_404(self) -> None:
        repo = FakeEnquiryRepo()
        repo.current = None
        with self.assertRaises(PartsIQError) as ctx:
            await add_message(actor(), uuid4(), self._body(), uuid4(), repo=repo)
        self.assertEqual(ctx.exception.code, "NOT_FOUND")

    async def test_duplicate_message_returns_existing(self) -> None:
        body = self._body(revision=1)
        enquiry_id = uuid4()
        existing = IdempotentMessage(payload_hash=canonical_hash(body), view=a_message_view(enquiry_id))
        repo = FakeEnquiryRepo(existing_message=existing, current=1)
        view = await add_message(actor(), enquiry_id, body, uuid4(), repo=repo)
        self.assertEqual(view.id, existing.view.id)
        self.assertEqual(repo.messages_added, 0)


class FakeUploadRepo:
    def __init__(self, attachment):
        self.attachment = attachment
        self.validated = False
        self.rejected = None

    async def get_attachment(self, actor, attachment_id):
        return self.attachment

    async def mark_validated(self, attachment_id):
        self.validated = True
        return AttachmentView(id=attachment_id, status="validated")

    async def mark_rejected(self, attachment_id, error_code):
        self.rejected = error_code
        return AttachmentView(id=attachment_id, status="rejected", error_code=error_code)


class ConfirmUpload(unittest.IsolatedAsyncioTestCase):
    async def test_nonexistent_is_404(self) -> None:
        async def fetch(_):
            return JPEG
        with self.assertRaises(PartsIQError) as ctx:
            await confirm_upload(actor(), uuid4(), repo=FakeUploadRepo(None), fetch_bytes=fetch)
        self.assertEqual(ctx.exception.code, "NOT_FOUND")

    async def test_valid_bytes_marked_validated(self) -> None:
        aid = uuid4()
        repo = FakeUploadRepo(PendingAttachment(aid, "image/jpeg", "pending"))

        async def fetch(_):
            return JPEG

        view = await confirm_upload(actor(), aid, repo=repo, fetch_bytes=fetch)
        self.assertEqual(view.status, "validated")
        self.assertTrue(repo.validated)

    async def test_wrong_magic_marked_rejected(self) -> None:
        aid = uuid4()
        repo = FakeUploadRepo(PendingAttachment(aid, "image/jpeg", "pending"))

        async def fetch(_):
            return b"not an image"

        view = await confirm_upload(actor(), aid, repo=repo, fetch_bytes=fetch)
        self.assertEqual(view.status, "rejected")
        self.assertEqual(repo.rejected, "UNSUPPORTED_MEDIA_TYPE")

    async def test_duplicate_confirmation_is_idempotent(self) -> None:
        aid = uuid4()
        repo = FakeUploadRepo(PendingAttachment(aid, "image/jpeg", "validated"))
        called = {"n": 0}

        async def fetch(_):
            called["n"] += 1
            return JPEG

        view = await confirm_upload(actor(), aid, repo=repo, fetch_bytes=fetch)
        self.assertEqual(view.status, "validated")
        self.assertEqual(called["n"], 0)  # no re-processing of an already-resolved attachment


if __name__ == "__main__":
    unittest.main(verbosity=2)
