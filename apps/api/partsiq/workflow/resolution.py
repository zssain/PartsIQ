"""The SEARCH / CHOOSE / PLAN resolution step handler (prompt 11 — F11/F22/F25/F26).

``resolve_items(state) -> ResolutionOutcome`` is the workflow step that, for each confirmed
item of a resolved machine configuration, asks the search service for the COMPATIBLE-ONLY
candidate set and decides — in ordinary Python — whether the item resolves to a single part,
needs a clarifying question (close/ambiguous set), or is handed to staff (no compatible part).
It returns the per-item :class:`~partsiq.core.api_models.MachineView`s and the single next
:class:`~partsiq.core.contracts.WorkflowStep` the fixed transition table should take.

Consolidated from the legacy orchestrator parts specialist + bounded tool session:

  * ``services/orchestrator/app/specialists/parts.py`` (``run_parts``): candidate ids come ONLY
    from the search service's compatible result set and the clarification code is chosen by
    tested score/margin thresholds — an LLM never introduces an incompatible part, changes a
    quantity or overrides low confidence (F22/F26). That decision now lives in
    :func:`partsiq.enquiries.questions.decide_ambiguity`.
  * ``services/orchestrator/app/tools.py`` (``ToolSession``): a per-step BOUNDED view that caps
    the number of search calls at :class:`SearchContext.max_calls` (≤ 4) and rejects a response
    whose catalogue version no longer matches the one the step started with — a stale catalogue
    is surfaced as ``STALE_CATALOGUE`` (409), never swallowed.

Only confirmed items drive matching (IMPLEMENTATION STEP 2): an item without a resolved
configuration asks for the model/serial rather than searching on an unconfirmed hint. Every
result is a typed value returned to the workflow, not a specialist-agent message (STEP 10). No
LLM decides compatibility, picks a part, or chooses the next step.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from partsiq.core.api_models import MachineView, ResolutionOutcome
from partsiq.core.contracts import (
    EnquiryState,
    ItemState,
    SearchContext,
    WorkflowStep,
)
from partsiq.core.errors import PartsIQError
from partsiq.enquiries.questions import decide_ambiguity

# The per-item search tool-call bound. The SearchContext already caps max_calls at 4
# (contract Field ge=0,le=4); this constant is the ceiling we never exceed even if a caller
# passed a larger value by mistake (defence in depth).
MAX_SEARCH_CALLS = 4


@dataclass(frozen=True, slots=True)
class CompatibleCandidates:
    """The compatible-only, score-ranked candidate ids for one item plus its ranking confidence.

    ``part_ids`` is ALREADY the compatibility-gated, ranked set the search service produced
    (``configuration_id`` guarantees the set is for the item's identified machine). ``top_score``
    and ``margin`` are the code-computed confidence over the full ranked set (F25). This handler
    never re-opens the compatibility gate; it only applies the score/margin thresholds.
    """

    configuration_id: int
    part_ids: list[int]
    top_score: float
    margin: float


class SearchGateway(Protocol):
    """The bounded, read-only search surface this step depends on (compatible-only results).

    The live adapter binds :class:`partsiq.search.service.SearchService` behind the fixed
    internal URL; tests inject a deterministic fake backed by the seed-42 fixture catalogue.
    ``active_catalogue_version`` is the catalogue version the serving cache currently reports,
    used to reject a step bound to a superseded version (stale catalogue -> 409).
    """

    @property
    def active_catalogue_version(self) -> UUID: ...

    async def search_parts(self, configuration_id: int, query: str) -> CompatibleCandidates: ...


class _BoundedSearch:
    """A per-step budget wrapper over the gateway (ported from the legacy ToolSession).

    Each ``search`` call is charged against the context's ``max_calls``; exceeding it raises
    ``QUOTA_EXCEEDED``. Before every call the gateway's active catalogue version is checked
    against the one the step started with; a mismatch raises ``STALE_CATALOGUE`` (409) so an
    unavailable/moved catalogue version is surfaced, not swallowed.
    """

    def __init__(self, gateway: SearchGateway, context: SearchContext) -> None:
        self._gateway = gateway
        self._context = context
        self._budget = min(context.max_calls, MAX_SEARCH_CALLS)
        self._calls = 0

    @property
    def calls(self) -> int:
        return self._calls

    def _ensure_current(self) -> None:
        if self._gateway.active_catalogue_version != self._context.catalogue_version_id:
            raise PartsIQError(
                "STALE_CATALOGUE",
                detail="The catalogue version changed while resolving this enquiry.",
                internal_detail=(
                    f"step started on catalogue {self._context.catalogue_version_id} but the "
                    f"active version is now {self._gateway.active_catalogue_version}"
                ),
            )

    def _charge(self) -> None:
        self._calls += 1
        if self._calls > self._budget:
            raise PartsIQError(
                "QUOTA_EXCEEDED",
                detail="Too many search attempts for this item.",
                internal_detail=f"search tool-call budget of {self._budget} exceeded",
            )

    async def search(self, configuration_id: int, query: str) -> CompatibleCandidates:
        self._ensure_current()
        self._charge()
        return await self._gateway.search_parts(configuration_id, query)


def _machine_view(
    item: ItemState,
    state: EnquiryState,
    search_state: str,
    configuration_id: int | None,
) -> MachineView:
    """Build the per-item :class:`MachineView` for the outcome.

    ``state`` here is the item's resolution state as the search step sees it:
    ``resolved`` (a single confident part), ``ambiguous`` (close set -> a question),
    ``not_found`` (no compatible part -> staff) or ``needs_serial`` (machine not yet identified).
    """
    assert state.catalogue_version_id is not None  # a search step always has an active version
    return MachineView(
        item_id=item.id,
        revision=state.revision,
        state=search_state,  # type: ignore[arg-type]
        configuration_id=configuration_id,
        model_text=item.request.model_text,
        serial_text=item.request.serial_text,
        catalogue_version_id=state.catalogue_version_id,
    )


@dataclass(frozen=True, slots=True)
class _ItemResolution:
    view: MachineView
    item: ItemState


def _apply(item: ItemState, decision_action: str, part_ids: list[int], status: str) -> ItemState:
    """Return a copy of the item with the step's candidate set / selection / status applied."""
    selected = part_ids[0] if (decision_action == "resolve" and part_ids) else None
    return item.model_copy(
        update={
            "candidate_part_ids": part_ids,
            "selected_part_id": selected,
            "status": status,
        }
    )


async def _resolve_item(
    item: ItemState,
    state: EnquiryState,
    search: _BoundedSearch,
) -> _ItemResolution:
    """Resolve one confirmed item: search compatible-only, then apply code thresholds (F26)."""
    # Unconfirmed OCR hints cannot trigger matching (STEP 2): without a resolved configuration
    # the machine is not identified, so ask for the model/serial rather than guessing.
    if item.configuration_id is None:
        return _ItemResolution(
            view=_machine_view(item, state, "needs_serial", None),
            item=_apply(item, "needs_staff", [], "needs_information"),
        )

    candidates = await search.search(item.configuration_id, item.request.description)
    decision = decide_ambiguity(
        candidates.part_ids,
        top_score=candidates.top_score,
        margin=candidates.margin,
    )

    if decision.action == "resolve":
        return _ItemResolution(
            view=_machine_view(item, state, "resolved", item.configuration_id),
            item=_apply(item, "resolve", decision.candidate_part_ids, "ready"),
        )
    if decision.action == "clarify":
        return _ItemResolution(
            view=_machine_view(item, state, "ambiguous", item.configuration_id),
            # A close/ambiguous set carries its top candidates forward for the CHOOSE step; the
            # item needs a customer decision and is never auto-picked (F26).
            item=_apply(item, "clarify", decision.candidate_part_ids, "needs_information"),
        )
    # needs_staff: no compatible candidate at all.
    return _ItemResolution(
        view=_machine_view(item, state, "not_found", item.configuration_id),
        item=_apply(item, "needs_staff", [], "unavailable"),
    )


def _next_step(items: list[ItemState]) -> WorkflowStep:
    """Pick the single next workflow step from the resolved item statuses.

    A close/ambiguous item takes the whole enquiry to CHOOSE (customer distinguishes); an item
    with no compatible part takes it to NEEDS_STAFF; otherwise every item resolved to one part
    and the enquiry proceeds to PLAN. This mirrors the WORKFLOW.md ``search`` edges: close
    candidates -> choose, no compatible result -> needs_staff, unique sufficient match -> plan.
    """
    if any(item.status == "needs_information" for item in items):
        return WorkflowStep.CHOOSE
    if any(item.status == "unavailable" for item in items):
        return WorkflowStep.NEEDS_STAFF
    return WorkflowStep.PLAN


async def resolve_items(
    state: EnquiryState,
    *,
    gateway: SearchGateway,
) -> ResolutionOutcome:
    """The SEARCH step: resolve every confirmed item to compatible candidates, return the outcome.

    For each item with a resolved configuration, the compatible-only candidate set is fetched
    through a bounded search session (≤ ``max_calls`` ≤ 4 per item; stale catalogue -> 409) and
    the resolve/clarify/needs_staff decision is made by code thresholds (F26). The returned
    :class:`ResolutionOutcome` carries the per-item :class:`MachineView`s and the next workflow
    step; the item statuses/selections are already applied so the fixed transition table can run.
    No LLM authorizes a part or decides the next step.
    """
    if state.catalogue_version_id is None:
        raise PartsIQError(
            "STALE_CATALOGUE",
            detail="No active catalogue version is available to resolve this enquiry.",
            internal_detail="enquiry state has no catalogue_version_id at the search step",
        )

    views: list[MachineView] = []
    resolved_items: list[ItemState] = []
    for item in state.items:
        # A fresh bounded session PER ITEM: each item gets its own ≤max_calls search budget,
        # exactly as the legacy per-stage ToolSession scoped the bound to one item's context.
        context = SearchContext(
            enquiry_id=state.enquiry_id,
            revision=state.revision,
            catalogue_version_id=state.catalogue_version_id,
            item_id=item.id,
            max_calls=MAX_SEARCH_CALLS,
        )
        search = _BoundedSearch(gateway, context)
        resolution = await _resolve_item(item, state, search)
        views.append(resolution.view)
        resolved_items.append(resolution.item)

    return ResolutionOutcome(items=views, next_step=_next_step(resolved_items))
