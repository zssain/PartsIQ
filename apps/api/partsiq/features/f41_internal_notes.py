"""F41 Internal notes facade (helpers ``review.append_note`` / ``review.list_notes``).

Append-only reviewer notes carrying author + timestamp, visible ONLY in the staff workspace. A
note NEVER appears in a customer-facing response or the approved PDF — the customer-facing
:class:`EnquiryView`/:class:`PublishedView` has no notes field and the export reads only the frozen
:class:`ApprovedSnapshot`. Only the assigned reviewer (or own-session demo reviewer) may read or
append; a foreign/unassigned actor gets NOT_FOUND (404). The body length is validated at the HTTP
boundary by :class:`~partsiq.core.api_models.NoteCreate` (1..4000 chars); the append is idempotent
on the request ``Idempotency-Key``. Access is ``review``.

Thin adapter over the injected :class:`StaffReviewSource`; the live append-only DB adapter (which
rejects UPDATE/DELETE on the notes table) is BLOCKED here.
"""
from __future__ import annotations

from uuid import UUID

from partsiq.core.api_models import NotePage, NoteView, PageQuery
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.features.f36_staff_inbox import (
    StaffReviewSource,
    require_staff_review,
    require_staff_role,
)


async def append_note(
    actor: ActorContext,
    enquiry_id: UUID,
    body: str,
    key: UUID,
    *,
    container: AppContainer,
    source: StaffReviewSource | None = None,
) -> NoteView:
    """Append a staff note (author + timestamp); assigned-only, append-only, idempotent."""
    require_staff_role(actor)
    source = source or require_staff_review(container)
    return await source.append_note(actor, enquiry_id, body, key)


async def list_notes(
    actor: ActorContext,
    enquiry_id: UUID,
    query: PageQuery,
    *,
    container: AppContainer,
    source: StaffReviewSource | None = None,
) -> NotePage:
    """List staff notes for an enquiry (assigned-only), in created_at/id order, keyset-paged."""
    require_staff_role(actor)
    source = source or require_staff_review(container)
    return await source.list_notes(actor, enquiry_id, query)
