"""F36 Staff inbox facade (helper ``review.list_assigned``), plus the shared staff-review read
port the staff-review features (F36/F37/F39/F41/F42/F43/F49) delegate to.

F36 lists the enquiries a staff member may act on — a reviewer sees only enquiries ASSIGNED to
them (plus their own active demo enquiries); an admin sees all. Status / priority / overdue /
free-text filters and stable keyset pagination are applied by the scoped store so a filtered page
can never leak a global total. Access is ``reviewer`` (admin implies reviewer scope).

Every staff-review read/write runs through the injected :class:`StaffReviewSource` port so each
facade is unit-testable offline with a deterministic fake + a reviewer actor. The live
PostgreSQL/RLS adapter is wired by the owner and is BLOCKED in this fixture/offline environment:
no staff store is configured, so :func:`require_staff_review` surfaces a clean 503 — and the demo
actor carries NO staff role (role switching in the demo UI is presentational only), so the role
gate below refuses a demo caller with FORBIDDEN before any store is consulted. A staff route
therefore never returns a 200 for a non-staff caller.

Role is taken ONLY from the server-trusted ``actor.roles`` (DB-sourced in production); a forged
``roles`` JWT claim can never reach here because the actor is built from the verified token's
subject plus a DB role lookup (:mod:`partsiq.auth.access`). No LLM authorizes a staff action.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from partsiq.core.api_models import (
    AssignmentView,
    AuditPage,
    DeadlineView,
    EnquiryPage,
    InboxQuery,
    NotePage,
    NoteView,
    PageQuery,
    PublishedView,
    ReviewView,
)
from partsiq.core.contracts import (
    ActorContext,
    ApprovalRequest,
    ApprovalResult,
    RejectionRequest,
    ReviewResult,
)
from partsiq.core.dependencies import AppContainer
from partsiq.core.errors import PartsIQError

# The staff roles honoured by the review surface. ``admin`` implies the reviewer scope, so an
# endpoint that requires ``review`` accepts either; an ``admin``-only endpoint (assignment)
# requires ``admin`` explicitly.
REVIEWER_ROLES: tuple[str, ...] = ("reviewer", "admin")


@runtime_checkable
class StaffReviewSource(Protocol):
    """Read/write port over the staff-review state (RLS/assignment-scoped in production).

    Every method authorises the actor against the enquiry (assigned reviewer, admin, or own active
    demo session) and raises NOT_FOUND for a foreign/unassigned enquiry so existence is never
    leaked. Writes (approve/reject/note/assign) mirror the committed DB invariants: approve only a
    verified current draft, reject records a reason and never publishes, notes are append-only and
    never surface to the customer, assignment moves access immediately, and the audit trail is
    append-only in event order. The live PostgreSQL adapter is BLOCKED in this environment.
    """

    async def list_assigned(self, actor: ActorContext, query: InboxQuery) -> EnquiryPage: ...

    async def get_workspace(self, actor: ActorContext, enquiry_id: UUID) -> ReviewView: ...

    async def approve(
        self, actor: ActorContext, request: ApprovalRequest, key: UUID
    ) -> ApprovalResult: ...

    async def reject(
        self, actor: ActorContext, request: RejectionRequest, key: UUID
    ) -> ReviewResult: ...

    async def append_note(
        self, actor: ActorContext, enquiry_id: UUID, body: str, key: UUID
    ) -> NoteView: ...

    async def list_notes(
        self, actor: ActorContext, enquiry_id: UUID, query: PageQuery
    ) -> NotePage: ...

    async def assign(
        self,
        actor: ActorContext,
        enquiry_id: UUID,
        assignee_id: UUID | None,
        expected_revision: int,
        key: UUID,
    ) -> AssignmentView: ...

    async def deadline(self, actor: ActorContext, enquiry_id: UUID) -> DeadlineView: ...

    async def read_published(self, actor: ActorContext, enquiry_id: UUID) -> PublishedView: ...

    async def list_audit(
        self, actor: ActorContext, enquiry_id: UUID, query: PageQuery
    ) -> AuditPage: ...


@dataclass(frozen=True, slots=True)
class _StaffNote:
    """A single append-only reviewer note (author + timestamp); never customer-visible."""

    id: UUID
    author_id: UUID
    body: str
    created_at: datetime


def require_staff_role(actor: ActorContext, *, admin_only: bool = False) -> None:
    """Refuse a non-staff caller with FORBIDDEN before any enquiry is loaded.

    Role comes only from the server-trusted ``actor.roles``. A demo caller has an empty role list,
    so this raises FORBIDDEN (403) — a staff route never returns a 200 to a non-staff caller, and
    the refusal reveals nothing about any specific enquiry. ``admin_only`` requires the ``admin``
    role (assignment is admin-only, F42); otherwise either ``reviewer`` or ``admin`` is accepted.
    """
    if admin_only:
        if "admin" not in actor.roles:
            raise PartsIQError("FORBIDDEN", internal_detail="this action is admin-only")
        return
    if not any(role in actor.roles for role in REVIEWER_ROLES):
        raise PartsIQError("FORBIDDEN", internal_detail="a reviewer or admin role is required")


def require_staff_review(container: AppContainer) -> StaffReviewSource:
    """Return the staff-review store, or raise a clean 503 when it is not configured.

    The staff-review state is DB-backed (assignments, decisions, notes, audit). In this
    fixture/offline environment it is not wired (the in-memory journey store tracks only the
    customer intake path, never a reviewer assignment or an approval), so a retryable 503 is
    surfaced — never a fabricated inbox, workspace or decision.
    """
    source = getattr(container, "staff_review", None)
    if source is None:
        raise PartsIQError(
            "DEPENDENCY_UNAVAILABLE",
            internal_detail="staff review state store is not configured in this environment",
        )
    return source


def resolve_review_source(
    container: AppContainer,
    actor: ActorContext,
    *,
    source: StaffReviewSource | None = None,
    admin_only: bool = False,
) -> StaffReviewSource:
    """Return the review source for the current mode, enforcing the right authorization boundary.

    FIXTURE mode: the in-memory journey IS the review source, authorised by OWN-DEMO-SESSION scope
    (the ``review`` access level; F03 role switching is presentational — same anonymous session).
    A demo caller reviews ONLY its own session's enquiries; a foreign/stale session is NOT_FOUND.

    DB mode: the role gate ALWAYS runs first — ``require_staff_role`` refuses a non-staff caller
    (403) even when a store is injected for testing — then the injected ``source`` or the live
    ``require_staff_review`` store (clean 503 until wired) is returned. Real RBAC is never weakened;
    the fixture branch only ever exposes own-session demo data.
    """
    if getattr(container, "is_fixture", False) and getattr(container, "journey", None) is not None:
        return container.journey  # type: ignore[return-value]
    require_staff_role(actor, admin_only=admin_only)
    return source or require_staff_review(container)


async def list_assigned(
    actor: ActorContext,
    query: InboxQuery,
    *,
    container: AppContainer,
    source: StaffReviewSource | None = None,
) -> EnquiryPage:
    """List the caller's staff inbox within their access scope (reviewer/admin), keyset-paged.

    In the fixture demo this is the caller's OWN-SESSION review queue (F03/F04 own-demo scope).
    """
    source = resolve_review_source(container, actor, source=source)
    return await source.list_assigned(actor, query)
