"""F38 gateway correction adapter (owner: gateway).

A reviewer POSTs typed extracted-detail corrections; the gateway checks review access and
forwards to the orchestrator's internal correction endpoint (never applies the revision
itself). It stays decoupled from the orchestrator: it carries only the typed RevisionRequest.
The forwarder is injected; with none wired the route fails closed (503). BLOCKED here.
"""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from partsiq_common.contracts import ActorContext, Contract, ItemCorrection, RevisionRequest
from partsiq_common.errors import PartsIQError

_REVIEW_ROLES = frozenset({"reviewer", "admin"})


class CorrectionBody(Contract):
    expected_revision: int
    corrections: list[ItemCorrection]
    reason: str


class CorrectionForwarder(Protocol):
    async def forward_correction(self, actor: ActorContext, change: RevisionRequest) -> dict:
        """Call the orchestrator internal /internal/enquiries/correct with the signed actor."""
        ...


def _authorize_review(actor: ActorContext) -> None:
    if not (_REVIEW_ROLES & set(actor.roles)):
        raise PartsIQError("FORBIDDEN", internal_detail="correction requires review access")


async def request_correction(
    actor: ActorContext, enquiry_id: UUID, body: CorrectionBody, *, forwarder: CorrectionForwarder
) -> dict:
    """Validate review access and forward the typed correction to the orchestrator."""
    _authorize_review(actor)
    change = RevisionRequest(
        enquiry_id=enquiry_id,
        expected_revision=body.expected_revision,
        corrections=body.corrections,
        reason=body.reason,
    )
    return await forwarder.forward_correction(actor, change)
