"""F60 Missing-parts queue facade (helpers ``review.update_missing`` / ``review.list_missing``).

When the deterministic pipeline genuinely cannot resolve an item (an empty search — never a
fabricated stock figure), it is recorded ONCE in a missing-parts queue linked to its enquiry.
Assigned staff then move an item through ``investigating`` -> ``resolved`` / ``unavailable``, each
with a note. Two surfaces:

  * ``update_missing`` transitions a queue item with a mandatory note. RESOLVING REQUIRES a staff
    explanation (the ``MissingUpdate.note`` is contract-required, min length 1); a status change
    never creates a catalogue row and never invents stock. Optimistic on ``expected_revision``
    (a mismatch is a 409). Only the assigned reviewer may act (a foreign item is NOT_FOUND).
  * ``list_missing`` lists the reviewer's scoped missing-parts queue with the inbox filters,
    keyset-paged (read-only).

Access is ``review`` / ``reviewer``; a non-staff (demo) caller is refused by the role gate (403).
Thin adapter over an injected port; the live RLS-scoped DB adapter is BLOCKED offline, so a
reviewer gets a clean 503 rather than a fabricated queue.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from partsiq.core.api_models import InboxQuery, MissingPage, MissingUpdate, MissingView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.features._ops_ports import require_store
from partsiq.features.f36_staff_inbox import require_staff_role


@runtime_checkable
class MissingPartsSource(Protocol):
    """Review-scoped missing-parts port (resolve-needs-note; never fabricates stock)."""

    async def update_missing(
        self, actor: ActorContext, item_id: UUID, update: MissingUpdate
    ) -> MissingView: ...

    async def list_missing(self, actor: ActorContext, query: InboxQuery) -> MissingPage: ...


async def update_missing(
    actor: ActorContext,
    item_id: UUID,
    update: MissingUpdate,
    *,
    container: AppContainer,
    source: MissingPartsSource | None = None,
) -> MissingView:
    """Transition a missing-parts item with a mandatory note; resolve needs an explanation (review).

    Optimistic on ``update.expected_revision`` (a mismatch is a 409); only the assigned reviewer may
    act (a foreign item is NOT_FOUND). Never creates a catalogue row or invents stock.
    """
    require_staff_role(actor)
    source = source or require_store(container, "missing_parts")
    return await source.update_missing(actor, item_id, update)


async def list_missing(
    actor: ActorContext,
    query: InboxQuery,
    *,
    container: AppContainer,
    source: MissingPartsSource | None = None,
) -> MissingPage:
    """List the reviewer's scoped missing-parts queue, keyset-paged (reviewer access; read-only)."""
    require_staff_role(actor)
    source = source or require_store(container, "missing_parts")
    return await source.list_missing(actor, query)
