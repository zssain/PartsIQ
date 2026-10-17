"""Draft persistence and assembly (prompt 13 — F45; step 9 fact/revision binding).

A draft is the reviewable reply for one enquiry revision: the validated :class:`ReplySlots`,
the code-rendered preview, and — crucially — the canonical hash of the verified facts it was
rendered FROM. Binding the draft to that fact hash is what lets any material change
(new facts, new revision, new catalogue version → a different hash) invalidate the draft
instead of silently approving a reply that no longer matches the plan (prompt 13 step 9).

Exactly one draft exists per (enquiry, revision): the store mirrors the
``UNIQUE(enquiry_id, revision)`` index on the ``drafts`` table, so re-saving the same revision
replaces its single row rather than growing a history of stale drafts. The persistence store
is injected (a ``DraftStore`` Protocol) so this module is testable offline against an
in-memory fake; the live Postgres adapter is wired by the owner.

This module performs no model call and no rendering layout itself — it composes
:func:`partsiq.ai.reply.draft_reply` (slots) and :func:`partsiq.enquiries.renderer.render_reply`
(preview) and records the binding. Staff-authored edits arrive as the same ``ReplySlots`` and
go through the same ``validate_slots`` gate before they can be saved (prompt 13 step 6).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from partsiq.ai.reply import validate_slots
from partsiq.core.api_models import DraftView
from partsiq.core.contracts import Locale, ReplySlots, VerifiedFacts
from partsiq.core.errors import PartsIQError

from .facts import facts_sha256
from .renderer import render_reply


@dataclass(frozen=True, slots=True)
class StoredDraft:
    """A persisted draft bound to the exact verified facts it was rendered from.

    ``facts_sha256`` is the binding: when the enquiry's current verified facts hash to a
    different value, this draft is stale and must be regenerated before it can back an
    approval (prompt 13 step 9).
    """

    enquiry_id: UUID
    revision: int
    locale: Locale
    slots: ReplySlots
    rendered_preview: str
    facts_sha256: str


class DraftStore(Protocol):
    """Persistence boundary for the ``drafts`` table (UNIQUE(enquiry_id, revision)).

    ``upsert`` is idempotent per (enquiry, revision): saving the same revision twice keeps a
    single row. The live Postgres adapter is injected by the owner; tests inject a fake.
    """

    async def upsert(self, draft: StoredDraft) -> StoredDraft: ...

    async def load(self, enquiry_id: UUID, revision: int) -> StoredDraft | None: ...


def build_draft(slots: ReplySlots, facts: VerifiedFacts, locale: Locale) -> StoredDraft:
    """Validate the slots, render the preview IN CODE, and bind the draft to the facts hash.

    Both a model draft and a staff edit flow through here, so the digit/identifier content
    guard (``validate_slots``) runs before any draft — model- or staff-authored — is rendered
    or stored. The rendered preview is built by the code-owned renderer, never the model, and
    the draft carries the canonical hash of the facts it describes.
    """
    validate_slots(slots)  # same gate for model and staff prose (prompt 13 steps 4, 6)
    rendered = render_reply(slots, facts, locale)
    return StoredDraft(
        enquiry_id=facts.enquiry_id,
        revision=facts.revision,
        locale=locale,
        slots=slots,
        rendered_preview=rendered,
        facts_sha256=facts_sha256(facts),
    )


async def save_draft(
    slots: ReplySlots,
    facts: VerifiedFacts,
    locale: Locale,
    *,
    store: DraftStore,
) -> StoredDraft:
    """Build and persist the one draft for ``(facts.enquiry_id, facts.revision)``.

    The store's UNIQUE(enquiry_id, revision) guarantees a single draft per revision; a repeat
    save of the same revision replaces its row rather than appending a stale one.
    """
    draft = build_draft(slots, facts, locale)
    return await store.upsert(draft)


async def load_draft(
    enquiry_id: UUID, revision: int, *, store: DraftStore
) -> StoredDraft:
    """Load the single persisted draft for an (enquiry, revision), or raise NOT_FOUND."""
    draft = await store.load(enquiry_id, revision)
    if draft is None:
        raise PartsIQError(
            "NOT_FOUND",
            internal_detail=f"no draft for enquiry {enquiry_id} revision {revision}",
        )
    return draft


def draft_is_current(draft: StoredDraft, facts: VerifiedFacts) -> bool:
    """True iff the draft was rendered from facts that still hash identically.

    A new revision, changed plan or changed catalogue version yields a different fact hash, so
    a materially changed enquiry invalidates the draft (prompt 13 step 9).
    """
    return draft.facts_sha256 == facts_sha256(facts)


def build_draft_view(draft: StoredDraft, *, verification_passed: bool) -> DraftView:
    """Assemble the API :class:`DraftView` from a stored draft and its verification outcome.

    The slots and the already-rendered preview are returned as-is; ``verification_passed`` is
    the current verification result for the bound facts (decided by the code-owned gate, never
    the model).
    """
    return DraftView(
        revision=draft.revision,
        slots=draft.slots,
        rendered_preview=draft.rendered_preview,
        verification_passed=verification_passed,
    )
