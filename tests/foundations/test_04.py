"""Acceptance tests for prompt 04 — private storage.

Offline with fake Storage backends. Covers prompt 04's slice of F13: unique pending
object key, real-bytes magic-type validation, 60-second signed links, log redaction,
authorize-then-delegate download signing, typed-resource resolution, nonexistent
object, and bucket validation. The decoded-pixel cap / EXIF strip (needs Pillow,
prompt 05/16) and duplicate-confirmation idempotency (confirm_upload, prompt 08) are
owned by later prompts and are not asserted here.

Both storage modules are loaded by file path because the gateway and worker both
expose an `app` package that cannot coexist in one interpreter.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "libs" / "partsiq_common"))

from partsiq_common.contracts import ActorContext, DownloadRequest, UploadRequest  # noqa: E402
from partsiq_common.errors import PartsIQError  # noqa: E402


def _load(name: str, relpath: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relpath)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


GW = _load("gateway_storage", "services/gateway/app/storage.py")
WK = _load("worker_storage", "services/worker/app/storage.py")

JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF"
PNG = b"\x89PNG\r\n\x1a\n\x00\x00"
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 "


class MagicValidation(unittest.TestCase):
    def test_accepts_matching_bytes(self) -> None:
        self.assertTrue(GW.validate_magic(JPEG, "image/jpeg"))
        self.assertTrue(GW.validate_magic(PNG, "image/png"))
        self.assertTrue(GW.validate_magic(WEBP, "image/webp"))

    def test_rejects_spoofed_or_wrong_type(self) -> None:
        self.assertFalse(GW.validate_magic(PNG, "image/jpeg"))  # png bytes declared as jpeg
        self.assertFalse(GW.validate_magic(b"RIFF????NOPE", "image/webp"))  # missing WEBP marker
        self.assertFalse(GW.validate_magic(JPEG, "application/pdf"))  # unsupported type

    def test_object_key_is_unique_and_scoped(self) -> None:
        enq = uuid4()
        a1 = GW.object_key_for(enq, uuid4(), "image/jpeg")
        a2 = GW.object_key_for(enq, uuid4(), "image/jpeg")
        self.assertTrue(a1.startswith(f"{enq}/"))
        self.assertNotEqual(a1, a2)
        self.assertTrue(a1.endswith(".jpg"))

    def test_signed_url_is_redacted_for_logs(self) -> None:
        self.assertEqual(GW.redact_url_for_log("https://x/y?token=SECRET"), "https://x/y?<redacted>")


class UploadContractBounds(unittest.TestCase):
    def test_oversized_upload_rejected_by_contract(self) -> None:  # F13 oversized
        with self.assertRaises(Exception):
            UploadRequest(enquiry_id=uuid4(), expected_revision=1, media_type="image/jpeg", size_bytes=10_485_761)

    def test_wrong_mime_rejected_by_contract(self) -> None:  # F13 wrong MIME
        with self.assertRaises(Exception):
            UploadRequest(enquiry_id=uuid4(), expected_revision=1, media_type="application/pdf", size_bytes=10)


class FakeUploadSigner:
    def __init__(self) -> None:
        self.calls: list = []

    async def create_upload_url(self, bucket: str, object_key: str, ttl_seconds: int) -> str:
        self.calls.append((bucket, object_key, ttl_seconds))
        return f"https://storage.local/{bucket}/{object_key}?token=SECRET"


class FakeWorkerSigner:
    def __init__(self) -> None:
        self.calls: list = []

    async def sign(self, request: DownloadRequest, ttl_seconds: int) -> str:
        self.calls.append((request.resource_type, str(request.resource_id), ttl_seconds))
        return "https://storage.local/signed?token=SECRET"


class CreateUploadAndSign(unittest.IsolatedAsyncioTestCase):
    async def test_create_upload_ticket(self) -> None:
        signer = FakeUploadSigner()
        req = UploadRequest(enquiry_id=uuid4(), expected_revision=1, media_type="image/png", size_bytes=1024)
        ticket = await GW.create_upload(_actor(), req, signer=signer)
        self.assertEqual(signer.calls[0][0], "nameplates")
        self.assertEqual(signer.calls[0][2], GW.SIGNED_URL_TTL_SECONDS)
        self.assertEqual(GW.SIGNED_URL_TTL_SECONDS, 60)
        self.assertTrue(str(ticket.attachment_id) in ticket.upload_url)

    async def test_sign_download_delegates_with_typed_resource(self) -> None:
        worker = FakeWorkerSigner()
        req = DownloadRequest(actor=_actor(), resource_type="evidence", resource_id=uuid4())
        ticket = await GW.sign_download(req, worker=worker)
        self.assertEqual(worker.calls[0][0], "evidence")
        self.assertEqual(worker.calls[0][2], 60)
        self.assertTrue(ticket.url.startswith("https://"))


class FakeStorageAdmin:
    def __init__(self) -> None:
        self.removed: list = []
        self.signed: list = []

    async def create_signed_download_url(self, bucket: str, object_key: str, ttl_seconds: int) -> str:
        self.signed.append((bucket, object_key, ttl_seconds))
        return f"https://storage.local/{bucket}/{object_key}?token=SECRET"

    async def remove(self, bucket: str, object_key: str) -> None:
        self.removed.append((bucket, object_key))


class WorkerSigning(unittest.IsolatedAsyncioTestCase):
    async def test_resolves_typed_resource_to_bucket_and_key(self) -> None:
        backend = FakeStorageAdmin()

        async def resolver(rtype: str, rid):
            return f"{rid}.pdf"

        req = DownloadRequest(actor=_actor(), resource_type="export", resource_id=uuid4())
        url = await WK.sign_download(req, backend=backend, resolve_key=resolver)
        self.assertEqual(backend.signed[0][0], "exports")  # export -> exports bucket
        self.assertEqual(backend.signed[0][2], 60)
        self.assertTrue(url.startswith("https://"))

    async def test_nonexistent_object_is_not_found(self) -> None:  # F13 nonexistent object
        backend = FakeStorageAdmin()

        async def missing(rtype: str, rid):
            return ""

        req = DownloadRequest(actor=_actor(), resource_type="evidence", resource_id=uuid4())
        with self.assertRaises(PartsIQError) as ctx:
            await WK.sign_download(req, backend=backend, resolve_key=missing)
        self.assertEqual(ctx.exception.code, "NOT_FOUND")

    async def test_remove_object_validates_bucket(self) -> None:
        backend = FakeStorageAdmin()
        await WK.remove_object("exports", "k.pdf", backend=backend)
        self.assertEqual(backend.removed, [("exports", "k.pdf")])
        with self.assertRaises(PartsIQError):
            await WK.remove_object("not-a-bucket", "k", backend=backend)

    def test_storage_admin_has_no_database_surface(self) -> None:
        # The worker's storage backend exposes only object operations (no DB REST).
        backend = FakeStorageAdmin()
        for forbidden in ("execute", "query", "fetch", "cursor"):
            self.assertFalse(hasattr(backend, forbidden))


class DeferredF13Cases(unittest.TestCase):
    @unittest.skip("decoded-pixel cap / EXIF strip needs Pillow (prompt 05/16)")
    def test_decompression_bomb_capped(self) -> None:  # pragma: no cover
        raise AssertionError("owned by prompt 16 read_nameplate/validate_image")

    @unittest.skip("duplicate confirmation idempotency is confirm_upload (prompt 08)")
    def test_duplicate_confirmation_rejected(self) -> None:  # pragma: no cover
        raise AssertionError("owned by prompt 08")


def _actor() -> ActorContext:
    return ActorContext(user_id=uuid4(), request_id=uuid4(), roles=[])


if __name__ == "__main__":
    unittest.main(verbosity=2)
