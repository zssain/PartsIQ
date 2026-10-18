"""F18 Progress timeline facade (helper ``workflow.read_progress``).

Returns the caller's own enquiry progress: the current :class:`~partsiq.core.contracts.WorkflowStep`,
an optional human-readable ``wait_reason`` and the revision/timestamp. Access is ``owner``; a
foreign enquiry is NOT_FOUND. The step reflects the durable workflow state (``INTAKE`` right after
a fixture create, before the background worker advances it).
"""
from __future__ import annotations

from uuid import UUID

from partsiq.core.api_models import ProgressView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer


async def read_progress(
    actor: ActorContext, enquiry_id: UUID, *, container: AppContainer
) -> ProgressView:
    """Read the current workflow progress for the caller's own enquiry."""
    return await container.require_journey().read_progress(actor, enquiry_id)
