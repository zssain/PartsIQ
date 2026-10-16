"""OCR confirmation (prompt 16 — F15).

Contract: ``async def confirm_extraction(actor, enquiry_id, request: ConfirmExtraction) -> EnquiryView``.

The owner (or assigned reviewer, or own active demo session) confirms or corrects the
extracted identifiers. The confirmation is recorded with the actor and time, bound to the
expected revision (a stale confirmation is a 409), and the serial is stored exactly as
typed so leading zeros survive. A blank corrected serial routes to the missing-serial flow
rather than authorizing a match. Recording the confirmation and asking the orchestrator to
re-process (revise) happen atomically behind the injected port; the live DB/orchestrator
calls are integration work. Unconfirmed OCR never authorizes matching — only this recorded
confirmation does.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from partsiq_common.contracts import ActorContext, ConfirmExtraction, EnquiryView
from partsiq_common.errors import PartsIQError


@dataclass(frozen=True, slots=True)
class ExtractionRecord:
    enquiry_id: UUID
    extraction_id: UUID
    current_revision: int
    owner_id: UUID | None = None
    assigned_to: UUID | None = None
    session_id: UUID | None = None
    session_generation: int | None = None


class OcrConfirmationRepo(Protocol):
    async def load_extraction(self, enquiry_id: UUID, extraction_id: UUID) -> ExtractionRecord | None: ...

    async def record_confirmation(
        self, actor: ActorContext, enquiry_id: UUID, request: ConfirmExtraction, *, missing_serial: bool
    ) -> EnquiryView: ...


def _authorize(actor: ActorContext, record: ExtractionRecord) -> None:
    if record.session_id is not None:
        if actor.session_id == record.session_id and actor.session_generation == record.session_generation:
            return
        raise PartsIQError("NOT_FOUND", internal_detail="demo confirmation requires the own active session")
    if actor.user_id is not None and actor.user_id in (record.owner_id, record.assigned_to):
        return
    raise PartsIQError("NOT_FOUND", internal_detail="confirmation requires ownership or assignment")


async def confirm_extraction(
    actor: ActorContext,
    enquiry_id: UUID,
    request: ConfirmExtraction,
    *,
    repo: OcrConfirmationRepo,
) -> EnquiryView:
    record = await repo.load_extraction(enquiry_id, request.extraction_id)
    if record is None:
        raise PartsIQError("NOT_FOUND", internal_detail="extraction not found for enquiry")
    _authorize(actor, record)

    if request.expected_revision != record.current_revision:
        raise PartsIQError("STALE_REVISION", internal_detail="the enquiry changed; reload before confirming")

    # Leading zeros are preserved (serial_text is stored verbatim); a blank corrected serial
    # is not a valid identifier and routes to the missing-serial clarification flow.
    missing_serial = not request.serial_text.strip()
    return await repo.record_confirmation(actor, enquiry_id, request, missing_serial=missing_serial)
