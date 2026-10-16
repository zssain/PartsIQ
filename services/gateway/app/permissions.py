"""Server-side access control mirroring the database RLS policies.

Contract: ``async def require_access(actor, enquiry_id, action) -> None``.

Real enquiries are assigned-only (admin, or the assigned reviewer); demo enquiries are
reviewable only by the owner of the active session (F03/F04/F54). A foreign or
nonexistent enquiry is reported as NOT_FOUND (404), never 403, so existence is not
leaked (F03: another visitor's enquiry returns 404). The enquiry-access record is read
through an injected repository so the decision logic is testable without a database.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from partsiq_common.contracts import AccessAction, ActorContext
from partsiq_common.errors import PartsIQError


@dataclass(frozen=True, slots=True)
class EnquiryAccess:
    enquiry_id: UUID
    owner_id: UUID | None
    session_id: UUID | None
    session_generation: int | None
    assigned_to: UUID | None


AccessRepo = Callable[[UUID], Awaitable[EnquiryAccess | None]]


def _own_active_demo(actor: ActorContext, record: EnquiryAccess) -> bool:
    return (
        record.session_id is not None
        and record.owner_id == actor.user_id
        and actor.session_id == record.session_id
        and actor.session_generation == record.session_generation
    )


async def require_access(
    actor: ActorContext, enquiry_id: UUID, action: AccessAction, *, repo: AccessRepo
) -> None:
    record = await repo(enquiry_id)
    if record is None:
        raise PartsIQError("NOT_FOUND", internal_detail="enquiry not found")

    is_admin = "admin" in actor.roles
    is_reviewer = "reviewer" in actor.roles
    is_catalogue_admin = "catalogue_admin" in actor.roles

    if record.session_id is not None:
        # Demo enquiry: only the owner of the matching active session may see or review it.
        if not _own_active_demo(actor, record):
            raise PartsIQError("NOT_FOUND", internal_detail="foreign or stale demo enquiry")
        return  # own active demo: read and review allowed

    # Real enquiry.
    assigned = record.assigned_to is not None and record.assigned_to == actor.user_id
    can_read = is_admin or (assigned and is_reviewer)
    if not can_read:
        raise PartsIQError("NOT_FOUND", internal_detail="not assigned")

    if action == AccessAction.ASSIGN and not is_admin:
        raise PartsIQError("FORBIDDEN", internal_detail="assignment is admin-only")
    if action == AccessAction.IMPORT and not (is_admin or is_catalogue_admin):
        raise PartsIQError("FORBIDDEN", internal_detail="import requires catalogue admin")
