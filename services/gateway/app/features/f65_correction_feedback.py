"""F65 Correction feedback (owner: gateway; depends on 14, 21, 23, F63).

Lets an admin turn a REVIEWED before/after correction into an anonymized labelled evaluation
case, recording the curating reviewer and the source revision. The system never auto-trains on
unreviewed edits: an unreviewed correction cannot become ground truth (rejected). The exported
fixture carries only the controlled expected label (approved_expected) + provenance — never the
private customer text (structural: EvalCaseExport has no text field). A correction already
curated, or a reused case id, is a duplicate and rejected. Admin only.

Pure over an injected CorrectionFeedbackRepo; the live corrections/eval-case adapter is BLOCKED.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from partsiq_common.contracts import ActorContext, Contract
from partsiq_common.errors import PartsIQError

MAX_LABEL = 500


class F65Request(Contract):
    correction_id: UUID
    case_id: str
    approved_expected: str


class F65Result(Contract):
    case_id: str
    source_revision: int
    approved_by: UUID


@dataclass(frozen=True, slots=True)
class CorrectionRecord:
    correction_id: UUID
    reviewed: bool
    source_revision: int
    before: str
    after: str
    private_text: str  # present on the source, but NEVER exported


@dataclass(frozen=True, slots=True)
class CorrectionSummary:
    correction_id: UUID
    before: str
    after: str
    reviewed: bool
    source_revision: int


@dataclass(frozen=True, slots=True)
class EvalCaseExport:
    """The anonymized fixture written to the eval set. Deliberately has NO private-text field."""

    case_id: str
    approved_expected: str
    source_revision: int
    approved_by: UUID


class CorrectionFeedbackRepo(Protocol):
    async def list_authorized(self, actor: ActorContext) -> list[CorrectionSummary]: ...

    async def load_correction(self, actor: ActorContext, correction_id: UUID) -> CorrectionRecord | None: ...

    async def case_exists(self, case_id: str) -> bool: ...

    async def source_already_curated(self, correction_id: UUID) -> bool: ...

    async def save_eval_case(self, case: EvalCaseExport) -> None: ...


def _authorize_admin(actor: ActorContext) -> None:
    if "admin" not in actor.roles:
        raise PartsIQError("FORBIDDEN", internal_detail="curating eval cases requires admin")


async def list_corrections(actor: ActorContext, *, repo: CorrectionFeedbackRepo) -> list[CorrectionSummary]:
    """List the before/after corrections the actor is authorized to see."""
    return await repo.list_authorized(actor)


async def curate_correction(actor: ActorContext, request: F65Request, *, repo: CorrectionFeedbackRepo) -> F65Result:
    """Curate a reviewed correction into an anonymized labelled eval case (admin only)."""
    _authorize_admin(actor)
    if not request.approved_expected.strip() or len(request.approved_expected) > MAX_LABEL:
        raise PartsIQError("VALIDATION_FAILED", internal_detail="approved_expected must be a 1..500 char label")
    record = await repo.load_correction(actor, request.correction_id)
    if record is None:
        raise PartsIQError("NOT_FOUND", internal_detail="correction not found")
    if not record.reviewed:
        raise PartsIQError("CONFLICT", internal_detail="an unreviewed correction cannot become ground truth")
    if await repo.source_already_curated(request.correction_id):
        raise PartsIQError("CONFLICT", internal_detail="this correction is already a curated eval case")
    if await repo.case_exists(request.case_id):
        raise PartsIQError("CONFLICT", internal_detail="case id already exists")
    # Only the controlled label + provenance are exported — never record.private_text.
    export = EvalCaseExport(
        case_id=request.case_id,
        approved_expected=request.approved_expected,
        source_revision=record.source_revision,
        approved_by=actor.user_id,
    )
    await repo.save_eval_case(export)
    return F65Result(case_id=export.case_id, source_revision=export.source_revision, approved_by=export.approved_by)
