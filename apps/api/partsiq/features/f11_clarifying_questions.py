"""F11 Clarifying questions / append message facade (helper ``intake.append_message``).

Appends a customer message to the caller's own enquiry, enforcing ``expected_revision`` through
the real :func:`partsiq.enquiries.intake.append_message` domain function: a stale revision is a
409, a foreign/unknown enquiry is 404, and the append is idempotent per ``Idempotency-Key``. The
new message bumps the revision (invalidating derived results) and returns the committed view (202).
"""
from __future__ import annotations

from uuid import UUID

from partsiq.core.contracts import ActorContext, EnquiryView, MessageCreate
from partsiq.core.dependencies import AppContainer
from partsiq.core.errors import PartsIQError
from partsiq.enquiries.intake import append_message, deserialize_view, serialize_view


async def append(
    actor: ActorContext,
    enquiry_id: UUID,
    command: MessageCreate,
    key: UUID,
    *,
    container: AppContainer,
) -> EnquiryView:
    """Append a customer message under ``expected_revision``; return the committed view (202)."""
    journey = container.require_journey()
    adapters = container.fixture_adapters
    if adapters is None:  # pragma: no cover - fixture mode always wires adapters
        raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="intake adapters missing")
    return await append_message(
        actor,
        enquiry_id,
        command,
        key,
        store=journey,
        idempotency=adapters.idempotency,
        rate_limiter=adapters.rate_limiter,
        serialize=serialize_view,
        deserialize=deserialize_view,
    )
