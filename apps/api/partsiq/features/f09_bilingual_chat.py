"""F09 Bilingual chat / enquiry intake facade (helpers ``intake.create_enquiry`` / ``history.get_enquiry``).

``create`` runs the real :func:`partsiq.enquiries.intake.create_enquiry` domain function over the
container's injected adapters: the fail-closed rate limit runs BEFORE any write, the idempotency
key is resolved, and the enquiry + first message + synthetic extraction commit together in the
in-memory journey store. The returned :class:`EnquiryView` is a committed 202-style resource — it
does NOT wait for background identification. ``get`` returns the caller's own enquiry; a foreign
one is NOT_FOUND.
"""
from __future__ import annotations

from uuid import UUID

from partsiq.core.contracts import ActorContext, EnquiryCreate, EnquiryView
from partsiq.core.dependencies import AppContainer
from partsiq.enquiries.intake import create_enquiry, deserialize_view, serialize_view


async def create(
    actor: ActorContext, command: EnquiryCreate, key: UUID, *, container: AppContainer
) -> EnquiryView:
    """Create an enquiry and its first message atomically; return the committed view (202)."""
    journey = container.require_journey()
    adapters = container.fixture_adapters
    if adapters is None:  # pragma: no cover - fixture mode always wires adapters
        from partsiq.core.errors import PartsIQError

        raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="intake adapters missing")
    return await create_enquiry(
        actor,
        command,
        key,
        store=journey,
        idempotency=adapters.idempotency,
        rate_limiter=adapters.rate_limiter,
        serialize=serialize_view,
        deserialize=deserialize_view,
    )


async def get_enquiry(
    actor: ActorContext, enquiry_id: UUID, *, container: AppContainer
) -> EnquiryView:
    """Return the caller's own enquiry view; a foreign/stale enquiry is NOT_FOUND."""
    return await container.require_journey().get_enquiry(actor, enquiry_id)
