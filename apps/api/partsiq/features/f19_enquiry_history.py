"""F19 Enquiry history facade (helper ``history.list_enquiries``).

Returns the caller's OWN enquiry history newest-first, keyset-paginated, via the real
:func:`partsiq.enquiries.history.list_history` domain function over the journey store. Ownership is
derived from the verified actor (``user_id`` for a customer; ``session_id`` + active generation for
a demo) — never from a client-supplied owner id, so a foreign owner id is structurally impossible
to request. A demo reset bumps the generation and hides prior rows. Access is ``customer``.
"""
from __future__ import annotations

from partsiq.core.api_models import EnquiryPage, HistoryQuery
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.enquiries.history import list_history


async def list_enquiries(
    actor: ActorContext, query: HistoryQuery, *, container: AppContainer
) -> EnquiryPage:
    """List the caller's own enquiries, newest-first, with a next_cursor when more remain."""
    return await list_history(actor, query, repo=container.require_journey())
