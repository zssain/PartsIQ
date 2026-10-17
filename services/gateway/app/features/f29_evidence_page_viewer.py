"""F29 Evidence page viewer (owner: gateway; depends on 04, 06, 20).

Lets an assigned reviewer (or a demo reviewer on their own active session) open the exact cited
page of a compatibility document behind a short-lived, worker-signed PDF URL. The caller passes
a TYPED evidence_id — never a raw Storage key — which the server resolves (within the current
revision) to a document + page; an unknown/arbitrary id is rejected as NOT_FOUND. Customers are
never authorized here (they receive the citation reference only). Every document is labelled
synthetic. An expired link is simply re-issued by calling again after re-authorization.

Pure over an injected EvidenceStore; the worker Storage signer + live access adapter are BLOCKED.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from partsiq_common.contracts import ActorContext, Contract
from partsiq_common.errors import PartsIQError


class F29Request(Contract):
    enquiry_id: UUID
    evidence_id: UUID
    expected_revision: int


class F29Result(Contract):
    url: str
    page_number: int
    expires_at: datetime
    synthetic: bool


@dataclass(frozen=True, slots=True)
class ReviewAccess:
    revision: int
    assigned_to: UUID | None
    is_demo: bool
    session_id: UUID | None
    session_generation: int | None


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    document: str
    page_number: int
    storage_resource_id: UUID


@dataclass(frozen=True, slots=True)
class SignedDoc:
    url: str
    expires_at: datetime


class EvidenceStore(Protocol):
    async def load_access(self, actor: ActorContext, enquiry_id: UUID) -> ReviewAccess | None:
        """Return review access for this enquiry, or None if it is not visible to the actor."""
        ...

    async def resolve_evidence(self, enquiry_id: UUID, evidence_id: UUID, revision: int) -> EvidenceRef | None:
        """Resolve a TYPED evidence id to a document+page within the revision; None if unknown."""
        ...

    async def sign_pdf(self, evidence_ref: EvidenceRef) -> SignedDoc:
        """Ask the worker to mint a short-lived signed URL for the already-authorized resource."""
        ...


def _authorize(actor: ActorContext, access: ReviewAccess) -> None:
    """Assigned reviewer, or a demo reviewer on their OWN active session; else NOT_FOUND."""
    if access.is_demo:
        if actor.session_id != access.session_id or actor.session_generation != access.session_generation:
            raise PartsIQError("NOT_FOUND", internal_detail="demo evidence requires the own active session")
        return
    if access.assigned_to is None or access.assigned_to != actor.user_id:
        raise PartsIQError("NOT_FOUND", internal_detail="evidence requires an assignment to this reviewer")


async def open_evidence(actor: ActorContext, request: F29Request, *, store: EvidenceStore) -> F29Result:
    """Authorize, resolve the typed evidence id, and return a short-lived signed PDF link + page."""
    access = await store.load_access(actor, request.enquiry_id)
    if access is None:
        raise PartsIQError("NOT_FOUND", internal_detail="enquiry not visible to this actor")
    _authorize(actor, access)
    if request.expected_revision != access.revision:
        raise PartsIQError("STALE_REVISION", internal_detail="a newer revision exists; reopen the current review")
    evidence_ref = await store.resolve_evidence(request.enquiry_id, request.evidence_id, access.revision)
    if evidence_ref is None:
        raise PartsIQError("NOT_FOUND", internal_detail="evidence id does not resolve to a cited document")
    signed = await store.sign_pdf(evidence_ref)  # re-signing renews an expired link
    return F29Result(
        url=signed.url, page_number=evidence_ref.page_number, expires_at=signed.expires_at, synthetic=True
    )
