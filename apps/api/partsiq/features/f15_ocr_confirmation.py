"""F15 OCR confirmation facade (helper ``extraction.confirm_nameplate``).

The vision job's nameplate reading is a SUGGESTION, never accuracy (CONSTRAINTS rule 8): an
unconfirmed OCR extraction can never authorise machine matching — only this recorded HUMAN
confirmation can. The owner (or assigned reviewer, or own active demo session) confirms, optionally
CORRECTING the model/serial text; the serial is stored VERBATIM (leading zeros preserved) and a
blank corrected serial routes to the normal missing-serial clarification flow rather than
authorising a match or blocking forever (F15). A stale ``expected_revision`` is a 409.

The command's ``extraction_id`` resolves to the enquiry's ownership/revision facts, which the
domain helper :func:`partsiq.enquiries.extraction.authorize_confirmation` uses to re-authorise the
actor (foreign/stale → NOT_FOUND) and to reject a stale revision — the facade reuses that shared
decision logic rather than re-implementing it. The confirmation then commits and returns the
updated :class:`EnquiryView` (202, per the endpoint contract) through the injected
:class:`NameplateConfirmationStore` port (unit-testable with a fake). That store is DB-backed
(``enquiry_extractions`` + revision bump) and NOT configured in this fixture/offline environment,
so a clean 503 is surfaced rather than a fabricated confirmation — the live PostgreSQL adapter is
wired by the owner and BLOCKED here. Owner access; a foreign enquiry/extraction is NOT_FOUND.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from partsiq.core.contracts import ActorContext, ConfirmExtraction, EnquiryView
from partsiq.core.dependencies import AppContainer
from partsiq.core.errors import PartsIQError
from partsiq.enquiries.extraction import ExtractionRecord, authorize_confirmation


@runtime_checkable
class NameplateConfirmationStore(Protocol):
    """Port over the one locked confirm-nameplate transaction (RLS/ownership-scoped in production).

    ``load_extraction`` returns the extraction's ownership/revision facts (``None`` when absent);
    ``commit`` records the confirmation (actor, time, serial VERBATIM; a blank serial routes to the
    missing-serial flow), bumps the revision, invalidates derived state and returns the committed
    enquiry view — atomically. The facade re-authorises the actor and checks the revision against
    the loaded record BEFORE calling ``commit``, so an unauthorised or stale confirm never mutates.
    """

    async def load_extraction(self, extraction_id: UUID) -> ExtractionRecord | None: ...

    async def commit(
        self, actor: ActorContext, command: ConfirmExtraction, *, missing_serial: bool
    ) -> EnquiryView: ...


def _require_confirmation_store(container: AppContainer) -> NameplateConfirmationStore:
    store = getattr(container, "nameplate_confirmation", None)
    if store is None or not hasattr(store, "commit"):
        raise PartsIQError(
            "DEPENDENCY_UNAVAILABLE",
            internal_detail="nameplate-confirmation store is not configured in this environment",
        )
    return store


async def confirm_nameplate(
    actor: ActorContext,
    enquiry_id: UUID,
    command: ConfirmExtraction,
    *,
    container: AppContainer,
    store: NameplateConfirmationStore | None = None,
) -> EnquiryView:
    """Record the human confirmation/correction of an OCR extraction; return the view (202)."""
    store = store or _require_confirmation_store(container)
    record = await store.load_extraction(command.extraction_id)
    if record is None or record.enquiry_id != enquiry_id:
        raise PartsIQError("NOT_FOUND", internal_detail="extraction not found for enquiry")
    authorize_confirmation(actor, record)
    if command.expected_revision != record.current_revision:
        raise PartsIQError(
            "STALE_REVISION", internal_detail="the enquiry changed; reload before confirming"
        )
    # Serial is stored VERBATIM; a blank/whitespace-only corrected serial routes to the normal
    # missing-serial clarification flow rather than authorising a match (F15).
    serial = command.serial_text
    missing_serial = serial is None or not serial.strip()
    return await store.commit(actor, command, missing_serial=missing_serial)
