"""Human confirmation of an OCR extraction (prompt 16 — F15).

Ported and consolidated from ``services/gateway/app/ocr_confirmation.py`` onto the single
``partsiq`` package, and re-targeted to produce the ``ExtractionView`` REST model.

Contract: ``async def confirm_extraction(actor, command, *, repo) -> ExtractionView``.

Model confidence is NEVER accuracy (CONSTRAINTS rule 8): an unconfirmed OCR extraction can
never authorize machine matching — only this recorded human confirmation can. The owner, the
assigned reviewer, or the owner of the matching active demo session may confirm or correct
the identifiers; anyone else gets NOT_FOUND (404) so existence is never leaked. A stale
confirmation (the enquiry moved on) is rejected with STALE_REVISION (409, F15).

The serial is stored EXACTLY as typed so leading zeros survive — it is never normalised
here. A blank corrected serial is not a valid identifier: it routes to the normal
missing-serial clarification flow rather than authorizing a match or blocking confirmation
forever (F15). Recording the confirmation (actor, time, source attachment) and asking the
orchestrator to re-process happen atomically behind the injected port; the live DB /
orchestrator wiring is owner work (BLOCKED here), so the logic stays unit-testable offline.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from partsiq.core.api_models import ExtractionView
from partsiq.core.contracts import ActorContext, ConfirmExtraction
from partsiq.core.errors import PartsIQError


@dataclass(frozen=True, slots=True)
class ExtractionRecord:
    """The ownership/assignment + revision facts needed to authorise a confirmation.

    Loaded through the injected repository so the decision logic below never touches a
    database directly and stays unit-testable (mirrors :class:`partsiq.auth.access`).
    """

    enquiry_id: UUID
    extraction_id: UUID
    current_revision: int
    owner_id: UUID | None = None
    assigned_to: UUID | None = None
    session_id: UUID | None = None
    session_generation: int | None = None


class ExtractionRepository(Protocol):
    """Injected port over the confirmation transaction. asyncpg at runtime, fake in tests."""

    async def load_extraction(self, extraction_id: UUID) -> ExtractionRecord | None:
        """Return the extraction's ownership/revision facts, or ``None`` if absent.

        The command carries only the extraction id; the record it resolves to carries the
        enquiry id, revision and the ownership/session facts used to authorise the actor.
        """
        ...

    async def record_confirmation(
        self,
        actor: ActorContext,
        command: ConfirmExtraction,
        *,
        missing_serial: bool,
    ) -> ExtractionView:
        """Persist the confirmation (actor, time, source attachment) + updated view atomically.

        ``missing_serial`` tells the live adapter to route to the normal missing-serial
        clarification flow instead of marking the machine identifier complete. The returned
        :class:`ExtractionView` reflects the confirmed state (``confirmed`` True).
        """
        ...


def authorize_confirmation(actor: ActorContext, record: ExtractionRecord) -> None:
    """Owner, assigned reviewer, or own active demo session may confirm; else 404.

    A demo confirmation needs the same active session and generation; a real confirmation
    needs ownership or an assignment to this actor. Anything else is NOT_FOUND so a foreign
    or stale-session actor learns nothing (SECURITY: existence is never leaked).
    """
    if record.session_id is not None:
        if (
            actor.session_id == record.session_id
            and actor.session_generation == record.session_generation
        ):
            return
        raise PartsIQError(
            "NOT_FOUND", internal_detail="demo confirmation requires the own active session"
        )
    if actor.user_id is not None and actor.user_id in (record.owner_id, record.assigned_to):
        return
    raise PartsIQError(
        "NOT_FOUND", internal_detail="confirmation requires ownership or assignment"
    )


async def confirm_extraction(
    actor: ActorContext,
    command: ConfirmExtraction,
    *,
    repo: ExtractionRepository,
) -> ExtractionView:
    """Confirm or correct an OCR extraction; produce/update the :class:`ExtractionView`.

    Loads the extraction, authorises the actor (else 404), rejects a stale revision (409),
    then records the confirmation with the serial stored VERBATIM. A blank corrected serial
    routes to the missing-serial flow. The command carries the enquiry's extraction id and the
    expected revision; the actor is the trusted, server-built context (never a request body).
    """
    record = await repo.load_extraction(command.extraction_id)
    if record is None:
        raise PartsIQError("NOT_FOUND", internal_detail="extraction not found for enquiry")
    authorize_confirmation(actor, record)

    if command.expected_revision != record.current_revision:
        raise PartsIQError(
            "STALE_REVISION", internal_detail="the enquiry changed; reload before confirming"
        )

    # Leading zeros are preserved — the serial is stored exactly as typed (never normalised
    # here). A blank / whitespace-only corrected serial is not a valid identifier and routes
    # to the normal missing-serial clarification flow rather than authorizing a match.
    serial = command.serial_text
    missing_serial = serial is None or not serial.strip()
    return await repo.record_confirmation(actor, command, missing_serial=missing_serial)


__all__ = [
    "ExtractionRecord",
    "ExtractionRepository",
    "authorize_confirmation",
    "confirm_extraction",
]
