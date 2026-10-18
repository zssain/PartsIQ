"""F12 Conversation memory / message history facade (helper ``history.list_messages``).

Lists the messages of the caller's own enquiry, newest-first and bounded by ``limit``. Access is
``owner``; the journey store enforces ownership and returns NOT_FOUND for a foreign enquiry.
Pagination is bounded (a large history is a separate page); the fixture journey returns a single
page with ``next_cursor = None``.
"""
from __future__ import annotations

from uuid import UUID

from partsiq.core.api_models import MessagePage
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer


async def list_messages(
    actor: ActorContext, enquiry_id: UUID, *, limit: int, container: AppContainer
) -> MessagePage:
    """List the caller's own enquiry messages, newest-first, bounded by ``limit``."""
    return await container.require_journey().list_messages(actor, enquiry_id, limit=limit)
