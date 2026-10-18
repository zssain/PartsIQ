"""F42 HTTP adapter: PUT /v1/staff/enquiries/{enquiry_id}/assignment (200).

An admin assigns an active reviewer to an enquiry (or unassigns via ``assignee_id=null``); access
changes immediately once persisted. The body is :class:`AssignRequest` (``expected_revision`` +
``assignee_id``) and the request carries an ``Idempotency-Key``. Admin access; a reviewer-only or
non-staff caller is refused by the facade's role gate (403), and a foreign enquiry is NOT_FOUND.
Delegates to the ``f42_assignments`` facade.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from partsiq.core.api_models import AssignmentView, AssignRequest
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import (
    AppContainer,
    get_container,
    idempotency_key,
    require_actor,
    typed_body,
)
from partsiq.features import f42_assignments as facade

router = APIRouter(tags=["staff"])


@router.put(
    "/staff/enquiries/{enquiry_id}/assignment",
    response_model=AssignmentView,
    status_code=200,
    operation_id="f42_assign",
    summary="Assign or unassign a reviewer for an enquiry (admin-only)",
)
async def assign(
    enquiry_id: UUID,
    command: AssignRequest = Depends(typed_body(AssignRequest)),
    actor: ActorContext = Depends(require_actor),
    container: AppContainer = Depends(get_container),
    key: UUID = Depends(idempotency_key),
) -> AssignmentView:
    return await facade.assign(
        actor,
        enquiry_id,
        command.assignee_id,
        command.expected_revision,
        key,
        container=container,
    )
