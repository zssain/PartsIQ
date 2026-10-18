"""F56 Repeat enquiry facade (helper ``intake.repeat_enquiry``).

Re-asks a prior enquiry: it creates a BRAND-NEW enquiry (fresh id, revision 1) that copies ONLY
the customer's original request text and confirmed identification hints, plus the locale and
destination warehouse supplied on this request, then runs the full pipeline again from scratch. It
NEVER carries forward an approval, an allocation/plan, a draft reply or a signed file URL — those
are outcomes of the original review and would be stale or unauthorized, so a repeat is never
pre-approved and never reuses a cached decision as authoritative. The source must be OWNED by the
caller (ownership from the verified actor; a foreign id is NOT_FOUND) and the create is idempotent
on the request ``Idempotency-Key``.

Thin adapter over an injected port; the live DB adapter is BLOCKED offline, so the customer gets a
clean 503 rather than a fabricated repeat.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from partsiq.core.api_models import RepeatRequest
from partsiq.core.contracts import ActorContext, EnquiryView
from partsiq.core.dependencies import AppContainer
from partsiq.features._ops_ports import require_store


@runtime_checkable
class RepeatSource(Protocol):
    """Owner-scoped repeat port (copies text/hints/locale/destination only; no outcomes)."""

    async def repeat_enquiry(
        self, actor: ActorContext, source_enquiry_id: UUID, request: RepeatRequest, key: UUID
    ) -> EnquiryView: ...


async def repeat_enquiry(
    actor: ActorContext,
    source_enquiry_id: UUID,
    request: RepeatRequest,
    key: UUID,
    *,
    container: AppContainer,
    source: RepeatSource | None = None,
) -> EnquiryView:
    """Create a fresh enquiry from a prior one the caller owns; nothing pre-approved (owner access).

    Copies only the request text, confirmed hints, locale and destination; idempotent on the key.
    """
    source = source or require_store(container, "repeat_enquiries")
    return await source.repeat_enquiry(actor, source_enquiry_id, request, key)
