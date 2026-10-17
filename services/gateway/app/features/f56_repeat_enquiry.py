"""F56 Repeat enquiry (owner: gateway; depends on 09, 19, F19, F55).

Re-asks a prior enquiry: it copies ONLY the customer's original request text, locale,
destination and confirmed identification hints (model/serial) into a brand-new enquiry with a
fresh id and revision 1, links the origin in the audit trail, and lets the normal pipeline run
matching, stock and human review again from scratch.

It NEVER copies an approval, an allocation/plan, a draft reply, or a signed file URL — those
are outcomes of the original review and would be stale or unauthorized here. That exclusion is
structural: the RepeatSpec handed to the persistence adapter simply has no field for them, so
there is nothing to carry forward. Source ownership is required (foreign -> NOT_FOUND) and a
repeated submission is deduplicated on the idempotency key. The live adapter is BLOCKED.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from partsiq_common.contracts import Contract, EnquiryView, Locale
from partsiq_common.errors import PartsIQError


class F56Request(Contract):
    source_enquiry_id: UUID
    idempotency_key: UUID


class F56Result(Contract):
    enquiry: EnquiryView


@dataclass(frozen=True, slots=True)
class ConfirmedHint:
    description: str
    model_text: str | None
    serial_text: str | None


@dataclass(frozen=True, slots=True)
class RepeatSource:
    """The source enquiry as the store yields it — including the outcome fields we must NOT copy."""

    enquiry_id: UUID
    text: str
    locale: Locale
    destination_warehouse_id: int
    confirmed_hints: tuple[ConfirmedHint, ...] = ()
    # Present only so a test can prove they are dropped; never read by _build_spec:
    approval_id: UUID | None = None
    draft_id: UUID | None = None
    allocations: tuple = ()
    signed_file_urls: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RepeatSpec:
    """The safe subset copied into the new enquiry. Deliberately has no outcome fields."""

    source_enquiry_id: UUID
    text: str
    locale: Locale
    destination_warehouse_id: int
    confirmed_hints: tuple[ConfirmedHint, ...] = field(default_factory=tuple)


class RepeatRepository(Protocol):
    async def load_source(self, actor, source_enquiry_id: UUID) -> RepeatSource | None:
        """Return None for an enquiry the actor does not own (foreign id indistinguishable)."""
        ...

    async def create_repeat(self, actor, spec: RepeatSpec, idempotency_key: UUID) -> EnquiryView:
        """Idempotently create the new enquiry, append an origin audit event, and enqueue a start."""
        ...


def _build_spec(source: RepeatSource) -> RepeatSpec:
    # Copies the request + confirmed hints only. No approval/allocation/draft/signed URL is
    # even referenced here, so none can leak into the new enquiry.
    return RepeatSpec(
        source_enquiry_id=source.enquiry_id,
        text=source.text,
        locale=source.locale,
        destination_warehouse_id=source.destination_warehouse_id,
        confirmed_hints=source.confirmed_hints,
    )


async def repeat_enquiry(actor, request: F56Request, *, repo: RepeatRepository) -> F56Result:
    """Create a fresh enquiry from a prior one; run the full pipeline again (nothing pre-approved)."""
    source = await repo.load_source(actor, request.source_enquiry_id)
    if source is None:
        raise PartsIQError("NOT_FOUND", internal_detail="source enquiry not visible to this actor")
    spec = _build_spec(source)
    view = await repo.create_repeat(actor, spec, request.idempotency_key)
    return F56Result(enquiry=view)
