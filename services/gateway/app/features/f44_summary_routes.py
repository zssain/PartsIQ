"""F44 gateway summary adapter (owner: gateway).

A reviewer requests a staff-only conversation summary; the gateway checks review access and
forwards to the orchestrator internal summary endpoint (never summarizes inline). It returns
202 while processing; the current-revision summary is then read from the review view. Stays
decoupled from the orchestrator (carries only typed ids). Forwarder injected; 503 if unwired.
"""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from partsiq_common.contracts import ActorContext
from partsiq_common.errors import PartsIQError

_REVIEW_ROLES = frozenset({"reviewer", "admin"})


class SummaryForwarder(Protocol):
    async def forward_summary(self, actor: ActorContext, enquiry_id: UUID, expected_revision: int) -> dict:
        """Call the orchestrator /internal/enquiries/summary with the signed actor; returns a job/ack."""
        ...


def _authorize_review(actor: ActorContext) -> None:
    if not (_REVIEW_ROLES & set(actor.roles)):
        raise PartsIQError("FORBIDDEN", internal_detail="summary requires review access")


async def request_summary(
    actor: ActorContext, enquiry_id: UUID, expected_revision: int, *, forwarder: SummaryForwarder
) -> dict:
    """Validate review access and forward the summary request to the orchestrator."""
    _authorize_review(actor)
    return await forwarder.forward_summary(actor, enquiry_id, expected_revision)
