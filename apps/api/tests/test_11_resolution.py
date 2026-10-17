"""Foundation 11 acceptance: machine search resolution, clarifying questions and fulfilment.

Fully offline and deterministic. No LLM participates in any decision here: the compatible-only
candidate set, the score/margin clarification thresholds, the per-item search-call bound, the
stale-catalogue reject, the unavailable-choice 409 and the warehouse allocation are all decided
in ordinary Python. The live search service and stock/route store are BLOCKED (live HTTP /
asyncpg); deterministic fakes stand in, one of them backed by the committed seed-42 fixture
catalogue, and the live paths are SKIPPED rather than faked.

Ports the behaviour characterized by the legacy orchestrator tests
(``services/orchestrator/tests/features/test_f11.py``, ``test_f26.py``) and the fulfilment
planning characterized in ``services/search`` (F33/F34), re-expressed against the single-package
contracts (``ResolutionOutcome``, ``MachineView``, ``PlanView``, ``VerifiedItem``, ``Allocation``).
"""
from __future__ import annotations

import os
import unittest
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from partsiq.catalogue import fixtures as fx
from partsiq.core.contracts import (
    EnquiryState,
    ItemInput,
    ItemState,
    SearchContext,
    WorkflowStep,
)
from partsiq.core.errors import PartsIQError
from partsiq.enquiries.fulfilment import (
    FulfilmentInputs,
    PartDescriptor,
    StockReading,
    is_fresh,
    plan_enquiry,
    plan_items,
)
from partsiq.enquiries.questions import (
    AMBIGUITY_MARGIN,
    RESOLVE_MIN_SCORE,
    clarification,
    clarification_pair,
    decide_ambiguity,
    validate_selection,
)
from partsiq.workflow.resolution import (
    MAX_SEARCH_CALLS,
    CompatibleCandidates,
    resolve_items,
)

CATALOGUE = uuid4()
NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


# =========================================================================
# Helpers: typed state construction.
# =========================================================================
def _item(
    *,
    item_id: UUID | None = None,
    description: str = "fuel filter",
    quantity: str | None = "2",
    configuration_id: int | None = 100,
    candidate_part_ids: list[int] | None = None,
    selected_part_id: int | None = None,
    status: str = "unresolved",
) -> ItemState:
    return ItemState(
        id=item_id or uuid4(),
        request=ItemInput(
            description=description,
            quantity=Decimal(quantity) if quantity is not None else None,
            source_message_id=uuid4(),
            source_start=0,
            source_end=len(description),
        ),
        configuration_id=configuration_id,
        candidate_part_ids=candidate_part_ids or [],
        selected_part_id=selected_part_id,
        status=status,  # type: ignore[arg-type]
    )


def _state(items: list[ItemState], *, catalogue=CATALOGUE) -> EnquiryState:
    return EnquiryState(
        enquiry_id=uuid4(),
        revision=1,
        session_generation=None,
        catalogue_version_id=catalogue,
        items=items,
        step_count=1,
        pending_question=None,
        draft_id=None,
        verification_id=None,
        phase="search",
    )


class FakeGateway:
    """A deterministic :class:`SearchGateway`. Returns a canned compatible-only candidate set.

    Counts calls so the per-item bound is observable, and lets a test move the active catalogue
    version to prove the stale-catalogue reject.
    """

    def __init__(
        self,
        result: CompatibleCandidates,
        *,
        active_version: UUID = CATALOGUE,
    ) -> None:
        self._result = result
        self._active = active_version
        self.calls = 0

    @property
    def active_catalogue_version(self) -> UUID:
        return self._active

    async def search_parts(self, configuration_id: int, query: str) -> CompatibleCandidates:
        self.calls += 1
        return self._result


class LoopingGateway(FakeGateway):
    """A gateway a buggy caller could poll forever; used to prove the call bound bites."""

    async def search_parts(self, configuration_id, query):
        self.calls += 1
        return self._result


# =========================================================================
# Clarifying questions (F11) — code-owned bilingual prose.
# =========================================================================
class ClarifyingQuestions(unittest.TestCase):
    def test_questions_are_bilingual_and_code_owned(self):
        for reason in ("needs_serial", "needs_model", "ambiguous_part", "ambiguous_model", "mismatch"):
            en, ar = clarification_pair(reason)
            self.assertTrue(en and ar, reason)
            self.assertEqual(clarification(reason, "en"), en)
            self.assertEqual(clarification(reason, "ar"), ar)
            # The Arabic string actually carries Arabic script (not an English echo).
            self.assertTrue(any("؀" <= ch <= "ۿ" for ch in ar), reason)

    def test_unknown_reason_falls_back_to_model_request(self):
        self.assertEqual(clarification("not-a-code", "en"), clarification("needs_model", "en"))

    def test_none_reason_is_empty(self):
        self.assertEqual(clarification("none", "en"), "")


# =========================================================================
# Ambiguity decision (F26) — thresholds decide; close/empty sets never auto-pick.
# =========================================================================
class AmbiguityDecision(unittest.TestCase):
    def test_single_confident_candidate_resolves(self):
        decision = decide_ambiguity([10], top_score=0.95, margin=0.9)
        self.assertEqual(decision.action, "resolve")
        self.assertEqual(decision.candidate_part_ids, [10])
        self.assertEqual(decision.clarification_code, "none")

    def test_close_runner_up_is_a_question_not_a_guess(self):
        decision = decide_ambiguity([10, 11], top_score=0.62, margin=0.02)
        self.assertEqual(decision.action, "clarify")
        self.assertEqual(decision.clarification_code, "ambiguous_part")
        # Both close candidates are carried forward; neither is silently picked.
        self.assertEqual(decision.candidate_part_ids, [10, 11])

    def test_low_confidence_cannot_be_overridden_into_a_pick(self):
        decision = decide_ambiguity([10], top_score=0.25, margin=0.25)
        self.assertEqual(decision.action, "clarify")
        self.assertEqual(decision.clarification_code, "ambiguous_part")

    def test_no_compatible_candidate_goes_to_staff(self):
        decision = decide_ambiguity([], top_score=0.0, margin=0.0)
        self.assertEqual(decision.action, "needs_staff")
        self.assertEqual(decision.candidate_part_ids, [])

    def test_threshold_boundaries(self):
        # Exactly at the resolve floor with a wide margin -> resolve.
        self.assertEqual(decide_ambiguity([10], top_score=RESOLVE_MIN_SCORE, margin=0.9).action, "resolve")
        # Just below the floor -> clarify.
        self.assertEqual(
            decide_ambiguity([10], top_score=RESOLVE_MIN_SCORE - 0.001, margin=0.9).action, "clarify"
        )
        # Margin exactly at the ambiguity threshold is NOT ambiguous (strict <).
        self.assertEqual(
            decide_ambiguity([10, 11], top_score=0.9, margin=AMBIGUITY_MARGIN).action, "resolve"
        )

    def test_unavailable_choice_returns_409(self):
        with self.assertRaises(PartsIQError) as ctx:
            validate_selection([10, 11], 999)
        self.assertEqual(ctx.exception.http_status, 409)
        self.assertEqual(ctx.exception.code, "CONFLICT")

    def test_available_choice_is_accepted(self):
        self.assertIsNone(validate_selection([10, 11], 11))


# =========================================================================
# Resolution step (SEARCH) — compatible-only, bounded, stale reject, next step.
# =========================================================================
class ResolutionStep(unittest.IsolatedAsyncioTestCase):
    async def test_only_compatible_candidates_surface_and_resolve_to_plan(self):
        item = _item()
        gateway = FakeGateway(CompatibleCandidates(100, [10], top_score=0.95, margin=0.9))
        outcome = await resolve_items(_state([item]), gateway=gateway)
        self.assertEqual(outcome.next_step, WorkflowStep.PLAN)
        self.assertEqual(len(outcome.items), 1)
        self.assertEqual(outcome.items[0].state, "resolved")
        self.assertEqual(outcome.items[0].configuration_id, 100)

    async def test_ambiguous_set_asks_and_goes_to_choose(self):
        item = _item()
        gateway = FakeGateway(CompatibleCandidates(100, [10, 11], top_score=0.62, margin=0.02))
        outcome = await resolve_items(_state([item]), gateway=gateway)
        self.assertEqual(outcome.items[0].state, "ambiguous")
        # A close set is a question, never a guess (F26): the step does not advance to PLAN.
        self.assertEqual(outcome.next_step, WorkflowStep.CHOOSE)

    async def test_no_compatible_part_goes_to_needs_staff(self):
        item = _item()
        gateway = FakeGateway(CompatibleCandidates(100, [], top_score=0.0, margin=0.0))
        outcome = await resolve_items(_state([item]), gateway=gateway)
        self.assertEqual(outcome.items[0].state, "not_found")
        self.assertEqual(outcome.next_step, WorkflowStep.NEEDS_STAFF)

    async def test_unidentified_item_is_not_searched(self):
        # An item with no configuration must not trigger a search on an unconfirmed hint.
        item = _item(configuration_id=None)
        gateway = FakeGateway(CompatibleCandidates(0, [10], top_score=0.95, margin=0.9))
        outcome = await resolve_items(_state([item]), gateway=gateway)
        self.assertEqual(gateway.calls, 0)
        self.assertEqual(outcome.items[0].state, "needs_serial")
        self.assertEqual(outcome.next_step, WorkflowStep.CHOOSE)  # needs_information -> choose/clarify

    async def test_stale_catalogue_version_is_rejected_409(self):
        item = _item()
        gateway = FakeGateway(
            CompatibleCandidates(100, [10], top_score=0.95, margin=0.9),
            active_version=uuid4(),  # the active version has moved on
        )
        with self.assertRaises(PartsIQError) as ctx:
            await resolve_items(_state([item]), gateway=gateway)
        self.assertEqual(ctx.exception.http_status, 409)
        self.assertEqual(ctx.exception.code, "STALE_CATALOGUE")
        # It is surfaced BEFORE a search is charged, not swallowed into an empty result.
        self.assertEqual(gateway.calls, 0)

    async def test_missing_active_version_is_stale_catalogue(self):
        with self.assertRaises(PartsIQError) as ctx:
            await resolve_items(_state([_item()], catalogue=None), gateway=FakeGateway(
                CompatibleCandidates(100, [10], top_score=0.9, margin=0.9)
            ))
        self.assertEqual(ctx.exception.code, "STALE_CATALOGUE")

    async def test_search_call_bound_is_four_per_item(self):
        # The SearchContext contract caps max_calls at 4 at the TYPE boundary; prove it rejects a
        # larger value, and that a normal resolve stays well under the bound.
        from pydantic import ValidationError

        self.assertEqual(MAX_SEARCH_CALLS, 4)
        with self.assertRaises(ValidationError):
            SearchContext(
                enquiry_id=uuid4(), revision=1, catalogue_version_id=CATALOGUE,
                item_id=uuid4(), max_calls=5,
            )
        # A normal resolve issues exactly one search per item (no retry storm).
        a, b = _item(), _item()
        gateway = FakeGateway(CompatibleCandidates(100, [10], top_score=0.95, margin=0.9))
        await resolve_items(_state([a, b]), gateway=gateway)
        self.assertEqual(gateway.calls, 2)

    async def test_bounded_session_charges_and_trips_the_budget(self):
        # Drive the bounded session directly to prove the budget raises QUOTA_EXCEEDED.
        from partsiq.workflow.resolution import _BoundedSearch

        gateway = LoopingGateway(CompatibleCandidates(100, [10], top_score=0.9, margin=0.9))
        context = SearchContext(
            enquiry_id=uuid4(), revision=1, catalogue_version_id=CATALOGUE,
            item_id=uuid4(), max_calls=4,
        )
        session = _BoundedSearch(gateway, context)
        for _ in range(4):
            await session.search(100, "fuel filter")
        with self.assertRaises(PartsIQError) as ctx:
            await session.search(100, "fuel filter")
        self.assertEqual(ctx.exception.code, "QUOTA_EXCEEDED")
        self.assertEqual(session.calls, 5)


# =========================================================================
# Stock freshness (F35).
# =========================================================================
class StockFreshness(unittest.TestCase):
    def test_future_timestamp_is_not_fresh(self):
        self.assertFalse(is_fresh(NOW + timedelta(seconds=1), NOW, 3600))

    def test_within_limit_is_fresh(self):
        self.assertTrue(is_fresh(NOW - timedelta(seconds=3599), NOW, 3600))

    def test_older_than_limit_is_stale(self):
        self.assertFalse(is_fresh(NOW - timedelta(seconds=3601), NOW, 3600))


# =========================================================================
# Fulfilment planning (F17/F32/F33/F34) — local-first, shortage, integer transfer days.
# =========================================================================
def _descriptor(part_id: int) -> PartDescriptor:
    return PartDescriptor(
        part_id=part_id,
        part_number=f"VP-FF-{part_id}",
        name_en="fuel filter",
        name_ar="فلتر وقود",
        source_reference="SYNTH-VP-PB-VP-20 rev 1, section FILTERS",
        evidence_id=uuid4(),
    )


def _inputs(
    *,
    destination: int = 1,
    stock: list[StockReading],
    transfer_days: dict[tuple[int, int], int],
    parts: dict[int, PartDescriptor],
    now: datetime = NOW,
    max_age: int = 3600,
) -> FulfilmentInputs:
    return FulfilmentInputs(
        destination_warehouse_id=destination,
        stock=stock,
        transfer_days=transfer_days,
        parts=parts,
        now=now,
        max_age_seconds=max_age,
    )


class FulfilmentPlanning(unittest.TestCase):
    def test_all_local_zero_transfer_days(self):
        item = _item(quantity="3", selected_part_id=10, status="ready")
        inputs = _inputs(
            stock=[StockReading(10, 1, Decimal("5"), NOW)],
            transfer_days={},
            parts={10: _descriptor(10)},
        )
        [verified] = plan_items(_state([item]), inputs)
        self.assertEqual(len(verified.allocations), 1)
        self.assertEqual(verified.allocations[0].warehouse_id, 1)
        self.assertEqual(verified.allocations[0].quantity, Decimal("3"))
        self.assertEqual(verified.allocations[0].transfer_days, 0)
        self.assertEqual(verified.shortage, Decimal("0"))
        self.assertEqual(verified.allocations[0].stock_updated_at, NOW)

    def test_local_first_then_nearest_remote_by_transfer_days(self):
        # Local has 2, need 5. Two remotes: wh3 (1 day) has 10, wh2 (3 days) has 10. A single
        # remote that covers the remaining 3 is preferred, and the nearest is chosen.
        item = _item(quantity="5", selected_part_id=10, status="ready")
        inputs = _inputs(
            destination=1,
            stock=[
                StockReading(10, 1, Decimal("2"), NOW),
                StockReading(10, 2, Decimal("10"), NOW),
                StockReading(10, 3, Decimal("10"), NOW),
            ],
            transfer_days={(2, 1): 3, (3, 1): 1},
            parts={10: _descriptor(10)},
        )
        [verified] = plan_items(_state([item]), inputs)
        self.assertEqual(verified.shortage, Decimal("0"))
        local = verified.allocations[0]
        remote = verified.allocations[1]
        self.assertEqual((local.warehouse_id, local.quantity, local.transfer_days), (1, Decimal("2"), 0))
        self.assertEqual((remote.warehouse_id, remote.quantity, remote.transfer_days), (3, Decimal("3"), 1))
        self.assertTrue(all(isinstance(a.transfer_days, int) for a in verified.allocations))

    def test_shortage_is_explicit_when_stock_insufficient(self):
        item = _item(quantity="10", selected_part_id=10, status="ready")
        inputs = _inputs(
            stock=[StockReading(10, 1, Decimal("4"), NOW)],
            transfer_days={},
            parts={10: _descriptor(10)},
        )
        [verified] = plan_items(_state([item]), inputs)
        allocated = sum((a.quantity for a in verified.allocations), Decimal("0"))
        self.assertEqual(allocated, Decimal("4"))
        self.assertEqual(verified.shortage, Decimal("6"))

    def test_missing_transfer_route_is_not_invented(self):
        # Local short, remote has stock but there is NO stored route -> remote is unreachable,
        # so the item is short rather than promised with an invented lead time (F34).
        item = _item(quantity="5", selected_part_id=10, status="ready")
        inputs = _inputs(
            destination=1,
            stock=[
                StockReading(10, 1, Decimal("0"), NOW),
                StockReading(10, 2, Decimal("10"), NOW),
            ],
            transfer_days={},  # no route from 2 -> 1
            parts={10: _descriptor(10)},
        )
        [verified] = plan_items(_state([item]), inputs)
        self.assertEqual(verified.allocations, [])
        self.assertEqual(verified.shortage, Decimal("5"))

    def test_negative_net_stock_is_clamped_to_zero(self):
        item = _item(quantity="2", selected_part_id=10, status="ready")
        inputs = _inputs(
            stock=[StockReading(10, 1, Decimal("-3"), NOW)],
            transfer_days={},
            parts={10: _descriptor(10)},
        )
        [verified] = plan_items(_state([item]), inputs)
        self.assertEqual(verified.allocations, [])
        self.assertEqual(verified.shortage, Decimal("2"))

    def test_stale_stock_is_not_allocated(self):
        item = _item(quantity="2", selected_part_id=10, status="ready")
        inputs = _inputs(
            stock=[StockReading(10, 1, Decimal("5"), NOW - timedelta(seconds=7200))],
            transfer_days={},
            parts={10: _descriptor(10)},
            max_age=3600,
        )
        [verified] = plan_items(_state([item]), inputs)
        self.assertEqual(verified.allocations, [])
        self.assertEqual(verified.shortage, Decimal("2"))

    def test_two_items_same_part_share_one_pool_no_double_count(self):
        # Two lines request the same part; only 3 units exist. Demand is consolidated and planned
        # once, then distributed in ordinal order: the earlier line is fully served, the later
        # line takes only what is left.
        a = _item(quantity="2", selected_part_id=10, status="ready")
        b = _item(quantity="2", selected_part_id=10, status="ready")
        inputs = _inputs(
            stock=[StockReading(10, 1, Decimal("3"), NOW)],
            transfer_days={},
            parts={10: _descriptor(10)},
        )
        verified = plan_items(_state([a, b]), inputs)
        by_item = {v.item_id: v for v in verified}
        self.assertEqual(by_item[a.id].shortage, Decimal("0"))
        self.assertEqual(sum((x.quantity for x in by_item[a.id].allocations), Decimal("0")), Decimal("2"))
        self.assertEqual(by_item[b.id].shortage, Decimal("1"))
        self.assertEqual(sum((x.quantity for x in by_item[b.id].allocations), Decimal("0")), Decimal("1"))
        # Aggregate across the shared (part, warehouse) never exceeds stock (verification parity).
        total = sum(
            (x.quantity for v in verified for x in v.allocations), Decimal("0")
        )
        self.assertEqual(total, Decimal("3"))

    def test_only_ready_items_are_planned(self):
        ready = _item(quantity="1", selected_part_id=10, status="ready")
        pending = _item(quantity="1", selected_part_id=None, status="needs_information")
        inputs = _inputs(
            stock=[StockReading(10, 1, Decimal("5"), NOW)],
            transfer_days={},
            parts={10: _descriptor(10)},
        )
        verified = plan_items(_state([ready, pending]), inputs)
        self.assertEqual([v.item_id for v in verified], [ready.id])


class PlanEnquiryEntryPoint(unittest.IsolatedAsyncioTestCase):
    async def test_plan_enquiry_returns_typed_plan_view(self):
        item = _item(quantity="2", selected_part_id=10, status="ready")
        state = _state([item])
        inputs = _inputs(
            stock=[StockReading(10, 1, Decimal("5"), NOW)],
            transfer_days={},
            parts={10: _descriptor(10)},
        )

        class Source:
            async def load(self, _state):
                return inputs

        snapshot = uuid4()
        plan = await plan_enquiry(state, source=Source(), stock_snapshot_id=snapshot)
        self.assertEqual(plan.enquiry_id, state.enquiry_id)
        self.assertEqual(plan.revision, 1)
        self.assertEqual(plan.stock_snapshot_id, snapshot)
        self.assertEqual(len(plan.items), 1)
        self.assertEqual(plan.items[0].part_id, 10)


# =========================================================================
# Seed-42 fixture catalogue sanity: the fulfilment inputs we model match the
# committed fixture's warehouses/transfer routes (local-first is meaningful).
# =========================================================================
class FixtureCatalogueParity(unittest.TestCase):
    def test_fixture_has_three_warehouses_and_integer_transfer_routes(self):
        snapshot = fx.build_catalogue()
        grouped: dict[str, list] = {}
        for record in snapshot.records:
            grouped.setdefault(record.entity_type, []).append(record)
        warehouses = grouped["warehouses"]
        routes = grouped["warehouse_transfer_routes"]
        self.assertEqual(len(warehouses), 3)
        # Every stored route carries an INTEGER transfer_days (F34).
        self.assertTrue(routes)
        for route in routes:
            self.assertIsInstance(route.payload["transfer_days"], int)


@unittest.skipUnless(
    os.environ.get("PARTSIQ_LIVE_SEARCH") == "1",
    "live search service + stock/route store are BLOCKED; set PARTSIQ_LIVE_SEARCH=1 to run",
)
class LiveSearchResolution(unittest.IsolatedAsyncioTestCase):  # pragma: no cover
    async def test_live_resolution_path(self):
        raise AssertionError("live search/stock path is BLOCKED and must never run in CI")


if __name__ == "__main__":
    unittest.main(verbosity=2)
