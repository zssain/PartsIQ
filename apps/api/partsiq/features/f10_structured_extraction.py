"""F10 Structured extraction facade (helper ``extraction.read_current``).

Returns the current :class:`ExtractionView` for the caller's own enquiry: the parsed intake
(language, preferred locale, urgency, items) plus any nameplate OCR and whether a human has
confirmed the identifiers. Access is ``owner`` — the journey store enforces ownership and
returns NOT_FOUND for a foreign or stale-session enquiry (existence is never leaked). Model
confidence is NEVER accuracy; ``confirmed`` stays False until a human confirms (F15).
"""
from __future__ import annotations

from uuid import UUID

from partsiq.core.api_models import ExtractionView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer


async def read_current(
    actor: ActorContext, enquiry_id: UUID, *, container: AppContainer
) -> ExtractionView:
    """Read the current extraction for the caller's own enquiry."""
    return await container.require_journey().read_extraction(actor, enquiry_id)
