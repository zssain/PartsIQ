"""F42 Assignments (owner: gateway; depends on 03, 07, 20).

An admin assigns an active reviewer to an enquiry (or unassigns). The change is applied
atomically with an assignment_events history row, so access changes immediately: the previous
reviewer's next request fails the assigned-only check. Only an admin may assign (reviewers may
not); the assignee must be an ACTIVE reviewer (a disabled or non-reviewer target is rejected).
Demo review is unaffected — it stays session-scoped and never uses assignment. The enquiry is
locked and the expected revision compared (assignment itself does not bump the compatibility
revision). The write is idempotent on the request key.

Pure over an injected AssignmentRepository; the live locked Postgres transaction is BLOCKED.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from partsiq_common.contracts import ActorContext, Contract
from partsiq_common.errors import PartsIQError


class F42Request(Contract):
    enquiry_id: UUID
    assigned_to: UUID | None
    expected_revision: int
    idempotency_key: UUID


class F42Result(Contract):
    assigned_to: UUID | None
    assigned_at: datetime


@dataclass(frozen=True, slots=True)
class AssignmentState:
    revision: int
    assigned_to: UUID | None


@dataclass(frozen=True, slots=True)
class AssignmentRecord:
    assigned_to: UUID | None
    assigned_at: datetime


class AssignmentRepository(Protocol):
    async def load_assignment_state(self, enquiry_id: UUID) -> AssignmentState | None: ...

    async def is_active_reviewer(self, user_id: UUID) -> bool:
        """True only for an enabled user holding the reviewer role."""
        ...

    async def apply_assignment(
        self, actor: ActorContext, enquiry_id: UUID, assigned_to: UUID | None, idempotency_key: UUID
    ) -> AssignmentRecord:
        """Atomically set the assignee + append an assignment_events row; idempotent on the key."""
        ...


def _authorize_admin(actor: ActorContext) -> None:
    if "admin" not in actor.roles:
        raise PartsIQError("FORBIDDEN", internal_detail="only an admin may assign a reviewer")


async def assign_enquiry(actor: ActorContext, request: F42Request, *, repo: AssignmentRepository) -> F42Result:
    """Assign or unassign a reviewer; access changes immediately once persisted."""
    _authorize_admin(actor)
    state = await repo.load_assignment_state(request.enquiry_id)
    if state is None:
        raise PartsIQError("NOT_FOUND", internal_detail="enquiry not found")
    if request.expected_revision != state.revision:
        raise PartsIQError("STALE_REVISION", internal_detail="a newer revision exists; reload before assigning")
    if request.assigned_to is not None and not await repo.is_active_reviewer(request.assigned_to):
        raise PartsIQError("VALIDATION_FAILED", internal_detail="assignee must be an active reviewer")
    record = await repo.apply_assignment(actor, request.enquiry_id, request.assigned_to, request.idempotency_key)
    return F42Result(assigned_to=record.assigned_to, assigned_at=record.assigned_at)
