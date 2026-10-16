"""Acceptance tests for prompt 16 — nameplate vision job (foundation gate).

Offline: a fake vision client drives read_nameplate; Pillow decodes/validates real in-memory
images; the dispatcher handler registry is exercised; and the gateway OCR-confirmation use
case (loaded by file path to avoid the cross-service ``app`` name clash) is checked for
authorization, stale-revision 409 and the blank-serial missing-serial flow. Live OpenAI
vision, Storage and DB are BLOCKED. Covers F14, F15.
"""
from __future__ import annotations

import importlib.util
import io
import sys
import unittest
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "partsiq_common"))
sys.path.insert(0, str(REPO_ROOT / "services" / "worker"))

from app.dispatcher import get_handler, register_handler  # noqa: E402
from app.jobs.nameplate import read_nameplate, validate_image  # noqa: E402
from partsiq_common.contracts import (  # noqa: E402
    ActorContext,
    BudgetReservation,
    ConfirmExtraction,
    EnquiryView,
    JobLease,
    NameplateResult,
)
from partsiq_common.errors import PartsIQError  # noqa: E402


def _load_ocr():
    """Load the gateway use case by file path (its only imports are partsiq_common)."""
    path = REPO_ROOT / "services" / "gateway" / "app" / "ocr_confirmation.py"
    spec = importlib.util.spec_from_file_location("gateway_ocr_confirmation", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # needed so the slotted dataclass can resolve its module
    spec.loader.exec_module(module)
    return module


ocr = _load_ocr()
WHEN = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _png(w=48, h=24):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (120, 120, 120)).save(buf, format="PNG")
    return buf.getvalue()


def _budget():
    return BudgetReservation(id=uuid4(), account_id="acct", reserved_usd=Decimal("0.01"))


def _job(attachment_id):
    return JobLease(
        id=uuid4(), kind="nameplate", enquiry_id=uuid4(), revision=1, session_generation=None,
        lease_token=uuid4(), expires_at=WHEN + timedelta(seconds=45), attempt=1,
        payload={"attachment_id": str(attachment_id), "media_type": "image/png"},
    )


class FakeVision:
    def __init__(self, content):
        async def create(**kwargs):
            return SimpleNamespace(
                id="r", choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
            )

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


class NameplateVision(unittest.IsolatedAsyncioTestCase):
    async def test_extraction_overrides_attachment_and_requires_confirmation(self):
        attachment_id = uuid4()
        model_json = NameplateResult(attachment_id=uuid4(), model_text="VP-20", serial_text="007", issues=[]).model_dump_json()
        result = await read_nameplate(_job(attachment_id), _png(), budget=_budget(), client=FakeVision(model_json))
        self.assertEqual(str(result.attachment_id), str(attachment_id))
        self.assertTrue(result.confirmation_required)
        self.assertEqual(result.serial_text, "007")  # leading zeros preserved

    def test_validate_image_rejects_corrupt(self):
        with self.assertRaises(PartsIQError):
            validate_image(b"xxxx", "image/png")


class DispatcherRegistry(unittest.TestCase):
    def test_nameplate_handler_registered(self):
        register_handler("nameplate", read_nameplate)
        self.assertIs(get_handler("nameplate"), read_nameplate)


class FakeOcrRepo:
    def __init__(self, record):
        self._record = record
        self.recorded = None

    async def load_extraction(self, enquiry_id, extraction_id):
        return self._record

    async def record_confirmation(self, actor, enquiry_id, request, *, missing_serial):
        self.recorded = {"serial": request.serial_text, "missing_serial": missing_serial}
        return EnquiryView(
            id=enquiry_id, revision=request.expected_revision, status="processing", messages=[],
            item_ids=[], catalogue_version_id=None, updated_at=WHEN,
        )


def _record(owner_id, enquiry_id, extraction_id, revision=1):
    return ocr.ExtractionRecord(
        enquiry_id=enquiry_id, extraction_id=extraction_id, current_revision=revision, owner_id=owner_id,
    )


def _confirm(extraction_id, *, revision=1, serial="000150"):
    return ConfirmExtraction(extraction_id=extraction_id, expected_revision=revision, model_text="VP-20", serial_text=serial)


class OcrConfirmation(unittest.IsolatedAsyncioTestCase):
    async def test_owner_confirms_preserving_serial(self):  # F15 success
        owner, enquiry, extraction = uuid4(), uuid4(), uuid4()
        repo = FakeOcrRepo(_record(owner, enquiry, extraction))
        actor = ActorContext(user_id=owner, request_id=uuid4(), roles=[])
        view = await ocr.confirm_extraction(actor, enquiry, _confirm(extraction), repo=repo)
        self.assertEqual(view.status, "processing")
        self.assertEqual(repo.recorded["serial"], "000150")  # leading zeros intact
        self.assertFalse(repo.recorded["missing_serial"])

    async def test_foreign_visitor_gets_404(self):  # unauthorized
        owner, enquiry, extraction = uuid4(), uuid4(), uuid4()
        repo = FakeOcrRepo(_record(owner, enquiry, extraction))
        stranger = ActorContext(user_id=uuid4(), request_id=uuid4(), roles=[])
        with self.assertRaises(PartsIQError) as ctx:
            await ocr.confirm_extraction(stranger, enquiry, _confirm(extraction), repo=repo)
        self.assertEqual(ctx.exception.http_status, 404)

    async def test_stale_confirmation_409(self):  # stale-revision
        owner, enquiry, extraction = uuid4(), uuid4(), uuid4()
        repo = FakeOcrRepo(_record(owner, enquiry, extraction, revision=3))
        actor = ActorContext(user_id=owner, request_id=uuid4(), roles=[])
        with self.assertRaises(PartsIQError) as ctx:
            await ocr.confirm_extraction(actor, enquiry, _confirm(extraction, revision=1), repo=repo)
        self.assertEqual(ctx.exception.http_status, 409)

    async def test_blank_serial_triggers_missing_serial_flow(self):
        owner, enquiry, extraction = uuid4(), uuid4(), uuid4()
        repo = FakeOcrRepo(_record(owner, enquiry, extraction))
        actor = ActorContext(user_id=owner, request_id=uuid4(), roles=[])
        await ocr.confirm_extraction(actor, enquiry, _confirm(extraction, serial="   "), repo=repo)
        self.assertTrue(repo.recorded["missing_serial"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
