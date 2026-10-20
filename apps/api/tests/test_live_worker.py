"""Offline checks for the database-mode worker pieces (the live path is covered by
tests/integration/worker_e2e.py against real PostgreSQL + Redis + Supabase Storage)."""
from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from uuid import uuid4

from partsiq.api.workspace_api import _SAMPLE_PLATE
from partsiq.jobs.live import _fixture_plates, reply_html
from partsiq.workspace.records import AttachmentRecord, EnquiryRecord
from partsiq.workspace.runner import RunExecutor


def test_sample_nameplate_ships_inside_the_package() -> None:
    # The API image copies only apps/api/partsiq; the sample must live there.
    assert _SAMPLE_PLATE.exists()
    assert "partsiq" in _SAMPLE_PLATE.parts


def test_worker_fixture_vision_recognises_only_the_committed_sample() -> None:
    plates = _fixture_plates()
    assert plates[hashlib.sha256(_SAMPLE_PLATE.read_bytes()).hexdigest()] == ("CA-110", "800000")
    assert hashlib.sha256(b"any other image").hexdigest() not in plates


def test_export_reply_is_escaped_and_keeps_line_breaks() -> None:
    assert reply_html('Hi <script>alert(1)</script>\n• CA-AF-8973 & "x"') == 'Hi &lt;script&gt;alert(1)&lt;/script&gt;<br>• CA-AF-8973 &amp; &quot;x&quot;'


def _record_with_photo(storage_key: str | None) -> EnquiryRecord:
    now = datetime.now(UTC)
    record = EnquiryRecord(id=uuid4(), owner_id=uuid4(), session_id=None, session_generation=None, locale="en", destination_warehouse_id=1,
                           created_at=now, updated_at=now, revision=2, status="processing", language="en", urgency="normal")
    record.attachments = [AttachmentRecord(id=uuid4(), media_type="image/png", size_bytes=10, status="validated", storage_key=storage_key)]
    return record


class _Dispatcher:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def read(self, **kwargs: object) -> dict:
        self.calls.append(kwargs)
        return {"model_text": "CA-110", "serial_text": "800000", "issues": [], "source": "fixture"}


class _Ws:
    store = object()


def test_runner_asks_the_worker_only_for_stored_photos_in_database_mode() -> None:
    executor = RunExecutor.__new__(RunExecutor)
    dispatcher = _Dispatcher()
    executor.nameplates = dispatcher  # type: ignore[attr-defined]
    stored = _record_with_photo("account/e/a")
    reading = asyncio.run(executor._nameplate_reading(_Ws(), stored))  # type: ignore[arg-type]
    assert reading and reading["model_text"] == "CA-110"
    assert dispatcher.calls[0]["revision"] == 2 and dispatcher.calls[0]["object_key"] == "account/e/a"
    # No storage key (demo sandbox / in-memory) -> in-process fixture vision, no job.
    assert asyncio.run(executor._nameplate_reading(_Ws(), _record_with_photo(None))) is None  # type: ignore[arg-type]
    # No database store -> no job either.
    class _Mem:
        store = None
    assert asyncio.run(executor._nameplate_reading(_Mem(), stored)) is None  # type: ignore[arg-type]
    assert len(dispatcher.calls) == 1
