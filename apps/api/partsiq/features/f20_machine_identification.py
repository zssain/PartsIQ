"""F20 Machine identification facade (helper ``search.identify_machine``), plus the shared
per-item workflow read port the search/candidate/stock features (F20-F35) delegate to.

F20 returns the resolved machine state for ONE enquiry item: the configuration a confirmed
model/serial resolved to, or the precise reason it could not (``needs_serial`` / ``ambiguous`` /
``mismatch`` / ``not_found``). The identification algorithm (:mod:`partsiq.search.identification`)
is deterministic and never consults an LLM (F20/F21): identity is resolved BEFORE any compatible
part set is ranked.

Per-item workflow state (an item's resolved configuration, ranked candidates, chosen part, planned
stock) is held by the enquiry-state read store, which is DB-backed. That store is NOT configured in
this fixture/offline environment, so every per-item read here surfaces a clean 503
(``DEPENDENCY_UNAVAILABLE``) rather than inventing state. The facade stays a thin adapter over the
injected :class:`ItemStateSource` port, so each feature is unit-testable with a deterministic fake
(the live PostgreSQL adapter is wired by the owner and is BLOCKED here).
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from partsiq.core.api_models import (
    CandidateList,
    CompatibilityView,
    ExplanationView,
    FreshnessView,
    MachineView,
    MatchEvidenceView,
    MismatchView,
    PlanView,
    ReferenceList,
    StockView,
    TransferView,
)
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.core.errors import PartsIQError


@runtime_checkable
class ItemStateSource(Protocol):
    """Read port over the per-item enquiry workflow state (RLS/ownership-scoped in production).

    Every method authorises the actor against the enquiry (owner, assigned reviewer, or own active
    demo session) and raises NOT_FOUND for a foreign/stale enquiry or item so existence is never
    leaked. The live PostgreSQL adapter reads the enquiry's resolved identity, ranked candidates,
    selection, plan and stock snapshot for the current revision; it is BLOCKED in this environment.
    """

    async def read_machine(
        self, actor: ActorContext, enquiry_id: UUID, item_id: UUID
    ) -> MachineView: ...

    async def read_mismatch(
        self, actor: ActorContext, enquiry_id: UUID, item_id: UUID
    ) -> MismatchView: ...

    async def read_compatibility(
        self, actor: ActorContext, enquiry_id: UUID, item_id: UUID
    ) -> CompatibilityView: ...

    async def read_match_evidence(
        self, actor: ActorContext, enquiry_id: UUID, item_id: UUID
    ) -> MatchEvidenceView: ...

    async def read_candidates(
        self, actor: ActorContext, enquiry_id: UUID, item_id: UUID
    ) -> CandidateList: ...

    async def compare_candidates(
        self, actor: ActorContext, enquiry_id: UUID, item_id: UUID, part_ids: list[int]
    ) -> CandidateList: ...

    async def read_explanation(
        self, actor: ActorContext, enquiry_id: UUID, item_id: UUID
    ) -> ExplanationView: ...

    async def read_references(
        self, actor: ActorContext, enquiry_id: UUID, item_id: UUID
    ) -> ReferenceList: ...

    async def read_stock(
        self, actor: ActorContext, enquiry_id: UUID, item_id: UUID
    ) -> StockView: ...

    async def read_plan(self, actor: ActorContext, enquiry_id: UUID) -> PlanView: ...

    async def read_transfers(self, actor: ActorContext, enquiry_id: UUID) -> TransferView: ...

    async def read_freshness(self, actor: ActorContext, enquiry_id: UUID) -> FreshnessView: ...


def require_item_state(container: AppContainer) -> ItemStateSource:
    """Return the per-item workflow read store, or raise a clean 503 when it is not configured.

    The enquiry-state read store is DB-backed. In this fixture/offline environment it is not wired
    (the in-memory journey store tracks only intake, not resolved identity/candidates/stock), so a
    retryable 503 is surfaced — never a fabricated machine/candidate/stock result.
    """
    source = getattr(container, "item_state", None)
    if source is None:
        raise PartsIQError(
            "DEPENDENCY_UNAVAILABLE",
            internal_detail="per-item workflow state store is not configured in this environment",
        )
    return source


async def identify_machine(
    actor: ActorContext,
    enquiry_id: UUID,
    item_id: UUID,
    *,
    container: AppContainer,
    source: ItemStateSource | None = None,
) -> MachineView:
    """Return the resolved machine state for one enquiry item (owner access; 404 if foreign)."""
    source = source or require_item_state(container)
    return await source.read_machine(actor, enquiry_id, item_id)
