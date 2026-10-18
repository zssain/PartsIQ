"""F45 Reply drafting facade (helper ``drafts.save_slots``).

A reviewer edits the reply-slots draft (greeting / explanation / closing) for an enquiry before
approval. Saving stores the edited slots against the current revision, re-renders the preview and
RE-RUNS verification so the draft's ``verification_passed`` reflects the edited prose — a reviewer
can therefore never approve a draft that no longer passes. The save is optimistic: an
``expected_revision`` mismatch is a 409 (reload). It never publishes; publication is the separate
approve action (F39). The AI may PROPOSE slot text, but the reviewer owns the saved draft and no
LLM authorizes it. Access is ``review``; a foreign/unassigned actor gets NOT_FOUND (404) and a
non-staff (demo) caller is refused by the role gate first.

Thin adapter over an injected port; the live draft store is BLOCKED offline, so a reviewer gets a
clean 503 rather than a fabricated draft.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from partsiq.core.api_models import DraftEdit, DraftView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.features._ops_ports import require_store
from partsiq.features.f36_staff_inbox import require_staff_role


@runtime_checkable
class DraftSource(Protocol):
    """Review-scoped draft save port."""

    async def save_slots(
        self, actor: ActorContext, enquiry_id: UUID, edit: DraftEdit, key: UUID
    ) -> DraftView: ...


async def save_slots(
    actor: ActorContext,
    enquiry_id: UUID,
    edit: DraftEdit,
    key: UUID,
    *,
    container: AppContainer,
    source: DraftSource | None = None,
) -> DraftView:
    """Save the edited reply slots, re-render and re-verify; never publishes (review access).

    Optimistic on ``edit.expected_revision`` (a mismatch is a 409) and idempotent on the key.
    """
    require_staff_role(actor)
    source = source or require_store(container, "staff_review")
    return await source.save_slots(actor, enquiry_id, edit, key)
