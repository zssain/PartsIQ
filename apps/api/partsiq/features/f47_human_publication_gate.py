"""F47 Human publication gate facade (helper ``publication.read_approved``).

Returns the ONE approved recommendation the customer is allowed to see for their own enquiry: the
published recommendation message, the approving ``decision_id`` and the approved revision — or an
empty view when nothing has been approved yet. Only the human approval path ever publishes a
recommendation (:mod:`partsiq.enquiries.publication`), and the DB couples it to the approved
decision with a one-per-revision unique index, so this read can surface at most one. An unapproved
enquiry returns the empty view (``message=None``) rather than a draft — nothing unapproved ever
reaches the customer. No internal note is included; notes never surface here.

Access is ``owner``: the read store authorises the verified actor as the owner (or own active demo
session) and raises NOT_FOUND for a foreign/stale enquiry so existence is never leaked. The
published-reply store is DB-backed; in this fixture/offline environment it is not wired (the
in-memory journey never runs a reviewer approval, so there is genuinely no approved recommendation
to read), so :func:`require_published_source` surfaces a clean 503 rather than fabricating an
approved reply. Thin, injectable adapter so the facade is unit-testable with a deterministic fake.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from partsiq.core.api_models import PublishedView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.core.errors import PartsIQError


@runtime_checkable
class PublishedReplySource(Protocol):
    """Read port over the approved recommendation for the caller's OWN enquiry.

    Authorises the actor as the owner (or own active demo session) and raises NOT_FOUND for a
    foreign/stale enquiry so existence is never leaked. Returns the empty :class:`PublishedView`
    (``message=None``) when nothing has been approved for the current revision.
    """

    async def read_published(self, actor: ActorContext, enquiry_id: UUID) -> PublishedView: ...


def require_published_source(container: AppContainer) -> PublishedReplySource:
    """Return the published-reply read store, or raise a clean 503 when it is not configured.

    The approved-recommendation read is DB-backed. In this fixture/offline environment it is not
    wired (no reviewer approval ever runs offline, so there is no published recommendation to
    read), so a retryable 503 is surfaced — never a fabricated approved reply.
    """
    source = getattr(container, "publication", None)
    if source is None:
        raise PartsIQError(
            "DEPENDENCY_UNAVAILABLE",
            internal_detail="published-reply read store is not configured in this environment",
        )
    return source


async def read_approved(
    actor: ActorContext,
    enquiry_id: UUID,
    *,
    container: AppContainer,
    source: PublishedReplySource | None = None,
) -> PublishedView:
    """Return the caller's own approved recommendation, or the empty view (owner access; 404 foreign)."""
    source = source or require_published_source(container)
    return await source.read_published(actor, enquiry_id)
