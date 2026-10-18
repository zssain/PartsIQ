"""F34 Transfer estimates facade (helper ``fulfilment.transfer_evidence``).

Returns the inter-warehouse transfer routes that a plan may use for an enquiry: each row carries
the integer ``transfer_days`` from the stored route, or ``None`` when no route exists (a missing
route is surfaced as unavailable, never an invented one-day promise — F34). ``estimate_only`` is
always True: these are planning estimates, never a committed delivery date. Review access; a
foreign enquiry is NOT_FOUND.

Read through the shared :class:`ItemStateSource`; the DB-backed route store is not configured in
this environment, so a clean 503 is surfaced. Thin, injectable adapter.
"""
from __future__ import annotations

from uuid import UUID

from partsiq.core.api_models import TransferView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.features.f20_machine_identification import ItemStateSource, require_item_state


async def transfer_evidence(
    actor: ActorContext,
    enquiry_id: UUID,
    *,
    container: AppContainer,
    source: ItemStateSource | None = None,
) -> TransferView:
    """Return the transfer-route estimates available to the enquiry's plan (review access)."""
    source = source or require_item_state(container)
    return await source.read_transfers(actor, enquiry_id)
