"""F44 Conversation summary facade (helpers ``jobs.enqueue_summary`` / ``review.read_summary``).

A reviewer can request an AI-generated SUMMARY of a long enquiry conversation and later read it.
Two surfaces:

  * ``enqueue_summary`` queues a durable background job (never runs the model inline) for the given
    revision and returns the job handle; it is idempotent on the request ``Idempotency-Key`` so a
    double-click enqueues once. The summary is an ASSISTIVE artefact — it never authorizes a
    decision, never edits facts and is regenerated per revision.
  * ``read_summary`` returns the stored summary for the current revision and whether it is STALE
    (a newer revision exists), so the UI shows "summary out of date — regenerate" rather than a
    misleading summary of old facts. Read-only.

Both are ``review`` access; a foreign/unassigned actor gets NOT_FOUND (404) and a non-staff (demo)
caller is refused by the role gate first. Thin adapter over an injected port; the live job queue /
summary store is BLOCKED offline, so a reviewer gets a clean 503 rather than a fabricated summary.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from partsiq.core.api_models import JobView, RevisionOnly, SummaryView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.features._ops_ports import require_store
from partsiq.features.f36_staff_inbox import require_staff_role


@runtime_checkable
class SummarySource(Protocol):
    """Review-scoped summary enqueue/read port."""

    async def enqueue_summary(
        self, actor: ActorContext, enquiry_id: UUID, revision: int, key: UUID
    ) -> JobView: ...

    async def read_summary(self, actor: ActorContext, enquiry_id: UUID) -> SummaryView: ...


async def enqueue_summary(
    actor: ActorContext,
    enquiry_id: UUID,
    request: RevisionOnly,
    key: UUID,
    *,
    container: AppContainer,
    source: SummarySource | None = None,
) -> JobView:
    """Queue a durable summary job for the given revision; idempotent on the key (review access)."""
    require_staff_role(actor)
    source = source or require_store(container, "staff_review")
    return await source.enqueue_summary(actor, enquiry_id, request.expected_revision, key)


async def read_summary(
    actor: ActorContext,
    enquiry_id: UUID,
    *,
    container: AppContainer,
    source: SummarySource | None = None,
) -> SummaryView:
    """Return the stored summary for the current revision and whether it is stale (review access)."""
    require_staff_role(actor)
    source = source or require_store(container, "staff_review")
    return await source.read_summary(actor, enquiry_id)
