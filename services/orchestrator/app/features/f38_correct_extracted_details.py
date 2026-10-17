"""F38 Correct extracted details (owner: orchestrator; depends on 09, 14, 20).

A reviewer corrects only the TYPED extracted fields of an item (description / quantity /
model_text / serial_text — the fields of ItemCorrection). The enquiry is locked, the expected
revision compared, and the revision machinery from prompt 14 (app.revisions.revise) applies the
change: it increments the revision, appends an immutable snapshot, resets status to processing,
invalidates the derived selections/draft/approval and enqueues recomputation, recording before
and after. A correction can never set an approved status or invent a candidate/part fact — the
ItemCorrection schema has no field for either, so that is structurally impossible; a result that
somehow claims approval is refused here as defence in depth. An unknown/empty correction is a
422; a stale expected revision is a 409.

Pure over an injected RevisionRepository; the live locked Postgres transaction is BLOCKED.
"""
from __future__ import annotations

from app.revisions import RevisionRepository, revise
from partsiq_common.contracts import ActorContext, Contract, EnquiryView, ItemCorrection, RevisionRequest
from partsiq_common.errors import PartsIQError

# The only fields a correction may touch (mirrors ItemCorrection; no status, no part/candidate).
ALLOWED_CORRECTION_FIELDS = ("description", "quantity", "model_text", "serial_text")


class F38Request(Contract):
    change: RevisionRequest


class F38Result(Contract):
    enquiry: EnquiryView


def _validate_corrections(corrections: list[ItemCorrection]) -> None:
    for correction in corrections:
        if all(getattr(correction, field) is None for field in ALLOWED_CORRECTION_FIELDS):
            raise PartsIQError(
                "VALIDATION_FAILED", internal_detail="a correction must set at least one allowed field"
            )


async def correct_extraction(actor: ActorContext, request: F38Request, *, repo: RevisionRepository) -> F38Result:
    """Apply typed corrections through the locked revision machinery; never approves, never invents."""
    _validate_corrections(request.change.corrections)
    view = await revise(actor, request.change, repo=repo)  # lock + authorize + stale check + apply
    if view.status == "approved":
        # The revision path resets status to processing; a result claiming approval is a violation.
        raise PartsIQError("CONFLICT", internal_detail="a correction cannot directly set approved status")
    return F38Result(enquiry=view)
