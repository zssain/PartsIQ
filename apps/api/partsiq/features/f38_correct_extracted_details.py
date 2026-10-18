"""F38 Correct extracted details facade (helper ``revisions.correct_extraction``).

A reviewer corrects the structured facts the pipeline extracted (description / quantity /
model / serial) for an enquiry's items. A correction is a NEW compatibility revision: it records
the reviewer's edit and reason and RE-RUNS identification/verification from the corrected facts —
it can NEVER publish a reply or invent a fact on its own, and it can never approve. The corrected
view is returned so the workspace reloads at the new revision. Access is ``review`` (assigned
reviewer or own active demo session); a foreign/unassigned actor gets NOT_FOUND (404), never a 403
that leaks existence; a non-staff (demo) caller is refused by the role gate first.

Thin adapter over an injected correction port; the live locked DB transaction (which persists the
correction, bumps the revision and invalidates any prior approval, F40) is BLOCKED in this
fixture/offline environment, so a reviewer gets a clean 503. No LLM authorizes a correction.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from partsiq.core.contracts import ActorContext, EnquiryView, RevisionRequest
from partsiq.core.dependencies import AppContainer
from partsiq.features._ops_ports import require_store
from partsiq.features.f36_staff_inbox import require_staff_role


@runtime_checkable
class CorrectionSource(Protocol):
    """Review-scoped correction port (RLS/assignment-scoped in production)."""

    async def correct_extraction(
        self, actor: ActorContext, request: RevisionRequest, key: UUID
    ) -> EnquiryView: ...


async def correct_extraction(
    actor: ActorContext,
    request: RevisionRequest,
    key: UUID,
    *,
    container: AppContainer,
    source: CorrectionSource | None = None,
) -> EnquiryView:
    """Record a reviewer's fact correction as a new revision and re-run matching (review access).

    The correction is persisted and the compatibility revision bumped; it never publishes a reply
    and never approves. A double submit with the same ``Idempotency-Key`` applies once.
    """
    require_staff_role(actor)
    source = source or require_store(container, "staff_review")
    return await source.correct_extraction(actor, request, key)
