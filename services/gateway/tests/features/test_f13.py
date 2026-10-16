"""F13 Private uploads — confirmation validates the real bytes and magic type.

Exercises the gateway confirm_upload use case: a valid JPEG is validated, a wrong magic
type is rejected with a safe code, a nonexistent attachment is 404, and a duplicate
confirmation is idempotent. (Pixel-cap/EXIF handling is the worker's prompt-16 job.)
"""
from __future__ import annotations

import unittest
from uuid import uuid4

from app.uploads import PendingAttachment, confirm_upload
from partsiq_common.contracts import ActorContext, AttachmentView
from partsiq_common.errors import PartsIQError

JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF"
PNG = b"\x89PNG\r\n\x1a\n"


class FakeUploadRepo:
    def __init__(self, attachment):
        self._attachment = attachment
        self.rejected_with = None

    async def get_attachment(self, actor, attachment_id):
        return self._attachment

    async def mark_validated(self, attachment_id):
        return AttachmentView(id=attachment_id, status="validated", error_code=None)

    async def mark_rejected(self, attachment_id, error_code):
        self.rejected_with = error_code
        return AttachmentView(id=attachment_id, status="rejected", error_code=error_code)


def _actor():
    return ActorContext(user_id=uuid4(), request_id=uuid4(), roles=[])


def _pending(media_type="image/jpeg", status="pending"):
    return PendingAttachment(attachment_id=uuid4(), media_type=media_type, status=status)


class PrivateUploads(unittest.IsolatedAsyncioTestCase):
    async def test_valid_jpeg_is_validated(self):
        repo = FakeUploadRepo(_pending())
        view = await confirm_upload(_actor(), uuid4(), repo=repo, fetch_bytes=lambda _id: _async(JPEG))
        self.assertEqual(view.status, "validated")

    async def test_wrong_magic_is_rejected(self):
        att = _pending(media_type="image/jpeg")
        repo = FakeUploadRepo(att)
        view = await confirm_upload(_actor(), uuid4(), repo=repo, fetch_bytes=lambda _id: _async(PNG))
        self.assertEqual(view.status, "rejected")
        self.assertEqual(repo.rejected_with, "UNSUPPORTED_MEDIA_TYPE")

    async def test_nonexistent_attachment_is_404(self):
        repo = FakeUploadRepo(None)
        with self.assertRaises(PartsIQError) as ctx:
            await confirm_upload(_actor(), uuid4(), repo=repo, fetch_bytes=lambda _id: _async(JPEG))
        self.assertEqual(ctx.exception.http_status, 404)

    async def test_duplicate_confirmation_is_idempotent(self):
        repo = FakeUploadRepo(_pending(status="validated"))
        view = await confirm_upload(_actor(), uuid4(), repo=repo, fetch_bytes=lambda _id: _async(JPEG))
        self.assertEqual(view.status, "validated")  # returns resolved state without re-fetch


async def _async(value):
    return value


if __name__ == "__main__":
    unittest.main(verbosity=2)
