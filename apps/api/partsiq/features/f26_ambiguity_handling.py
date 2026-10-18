"""F26 Ambiguity handling / candidate choice facade (helper ``revisions.choose_candidate``).

When ranking is ambiguous (F25), a reviewer resolves it by CHOOSING one candidate for an item.
This is a mutating correction: it locks the enquiry, re-authorises the actor (owner / assigned
reviewer / own active demo session), checks ``expected_revision`` (a stale choice is a 409), and
only accepts a ``part_id`` that is in the item's COMPATIBLE candidate set — a part outside the
catalogue-derived compatible set is rejected, never silently selected (the F22 gate is never
bypassed). It then bumps the revision, invalidates the derived plan/draft/approval and returns the
committed :class:`EnquiryView` (202). Owner access; a foreign enquiry/item is NOT_FOUND. The choice
is idempotent per ``Idempotency-Key``.

Choosing a candidate mutates DB-backed enquiry-state that is NOT configured in this fixture/offline
environment, so the choice surfaces a clean 503 rather than a fabricated commit. The facade is a
thin adapter over the injected :class:`ChoiceStore` port (unit-testable with a fake; the live
PostgreSQL adapter is wired by the owner and BLOCKED here).
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from partsiq.core.api_models import CandidateChoice
from partsiq.core.contracts import ActorContext, EnquiryView
from partsiq.core.dependencies import AppContainer
from partsiq.core.errors import PartsIQError


@runtime_checkable
class ChoiceStore(Protocol):
    """Port over the one locked candidate-choice transaction (RLS/ownership-scoped in production).

    ``choose`` re-authorises the actor, compares ``expected_revision``, validates the ``part_id``
    against the item's compatible candidate set, increments the revision, resets derived state and
    returns the committed view — all atomically and idempotently per ``Idempotency-Key``.
    """

    async def choose(
        self,
        actor: ActorContext,
        enquiry_id: UUID,
        item_id: UUID,
        choice: CandidateChoice,
        key: UUID,
    ) -> EnquiryView: ...


def _require_choice_store(container: AppContainer) -> ChoiceStore:
    store = getattr(container, "item_state", None)
    if store is None or not hasattr(store, "choose"):
        raise PartsIQError(
            "DEPENDENCY_UNAVAILABLE",
            internal_detail="candidate-choice store is not configured in this environment",
        )
    return store


async def choose_candidate(
    actor: ActorContext,
    enquiry_id: UUID,
    item_id: UUID,
    choice: CandidateChoice,
    key: UUID,
    *,
    container: AppContainer,
    store: ChoiceStore | None = None,
) -> EnquiryView:
    """Choose a compatible candidate for an item under ``expected_revision``; return the view (202)."""
    store = store or _require_choice_store(container)
    return await store.choose(actor, enquiry_id, item_id, choice, key)
