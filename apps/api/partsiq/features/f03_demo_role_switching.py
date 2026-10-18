"""F03 Demo role switching facade.

Role switching in the demo is PRESENTATIONAL only: a demo caller may ask the UI to render the
customer or reviewer view of its OWN session's data, but switching never grants a server-side
staff role. This facade reports the roles the demo UI may present for the given actor — always
the UI-only pair for an own-session demo actor — without ever mutating the trusted
:class:`ActorContext`. There is no privileged endpoint for F03 in ``spec/endpoints.json``.
"""
from __future__ import annotations

from partsiq.core.contracts import ActorContext

#: The views a demo caller may switch between in the UI. These are presentational labels, not
#: server roles — ``require_access`` still authorises every action against the stored session.
DEMO_UI_VIEWS: tuple[str, ...] = ("customer", "reviewer")


def available_views(actor: ActorContext) -> list[str]:
    """Return the UI views the demo may switch between for ``actor`` (presentational only)."""
    _ = actor
    return list(DEMO_UI_VIEWS)
