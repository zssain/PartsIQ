"""F17 Multi-part enquiries facade (helper ``revisions.correct_items``).

An enquiry may carry up to 20 items (``ItemsEdit`` bounds 1..20), each with its own quantity,
machine/configuration, candidate set and selection. Correcting items is a REVISION: it locks the
enquiry, re-authorises the actor (owner / assigned reviewer / own active demo session), compares
``expected_revision`` (a stale edit is a 409), then increments the revision, appends an IMMUTABLE
snapshot and invalidates the derived selection/plan/draft/approval so every item recomputes under
the new revision. A historical approval is NEVER mutated (F40). Stock is planned ONCE across the
combined requested quantities per selected part and distributed in ordinal order — so two lines
requesting the same part cannot double-count available stock (F17); that recompute runs
downstream on the new revision, never inline here.

Delegates to the real :func:`partsiq.enquiries.revisions.revise` domain function over an injected
:class:`RevisionRepository`. ``ItemsEdit`` carries no free-text reason, so a fixed audit reason is
synthesised for the immutable snapshot. That repository is the DB-backed locked-correction
transaction (append-only ``enquiry_revisions``) and is NOT configured in this fixture/offline
environment, so a clean 503 is surfaced rather than a fabricated commit — the live PostgreSQL
adapter is wired by the owner and BLOCKED here. The returned :class:`EnquiryView` reflects the new
revision (200). Owner access; a foreign enquiry is NOT_FOUND.
"""
from __future__ import annotations

from uuid import UUID

from partsiq.core.api_models import ItemsEdit
from partsiq.core.contracts import ActorContext, EnquiryView, RevisionRequest
from partsiq.core.dependencies import AppContainer
from partsiq.core.errors import PartsIQError
from partsiq.enquiries.revisions import RevisionRepository, revise

# Fixed audit reason for an item correction submitted through the multi-part items editor. The
# ``ItemsEdit`` contract has no reason field, but the immutable revision snapshot requires one.
_CORRECTION_REASON = "multi-part items corrected via the items editor (F17)"


def _require_revision_repo(container: AppContainer) -> RevisionRepository:
    repo = getattr(container, "revision_repo", None)
    if repo is None or not hasattr(repo, "apply_revision"):
        raise PartsIQError(
            "DEPENDENCY_UNAVAILABLE",
            internal_detail="revision store is not configured in this environment",
        )
    return repo


async def correct_items(
    actor: ActorContext,
    enquiry_id: UUID,
    command: ItemsEdit,
    *,
    container: AppContainer,
    repo: RevisionRepository | None = None,
) -> EnquiryView:
    """Correct an enquiry's items as one revision; return the committed new-revision view (200)."""
    repo = repo or _require_revision_repo(container)
    request = RevisionRequest(
        enquiry_id=enquiry_id,
        expected_revision=command.expected_revision,
        corrections=list(command.items),
        reason=_CORRECTION_REASON,
    )
    return await revise(actor, request, repo=repo)
