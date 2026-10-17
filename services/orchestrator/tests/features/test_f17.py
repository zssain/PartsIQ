"""F17 Multi-part enquiries — independent per-item resolution + aggregate allocation.

Each item carries its own quantity, machine/configuration, candidate set, selection and
status. Stock is planned ONCE per selected part and distributed in ordinal order, so two
items requesting the same part cannot double count available stock. One unresolved item
blocks a final all-items approval; a non-positive quantity is rejected; at most 20 items.
"""
from __future__ import annotations

import unittest
from decimal import Decimal
from uuid import uuid4

from app.features.f17_multi_part_enquiries import (
    F17Request,
    ItemPlan,
    ItemPlanRow,
    can_approve_all,
    resolve_items,
)
from app.handlers import unresolved_items
from partsiq_common.contracts import ActorContext, EnquiryState, ItemInput, ItemState
from partsiq_common.errors import PartsIQError


def _actor(session_id=None, generation=None):
    return ActorContext(
        user_id=uuid4(), request_id=uuid4(), roles=["reviewer"],
        session_id=session_id, session_generation=generation,
    )


def _row(desc="fuel filter", qty=Decimal("2"), part=10, config=100, candidates=(10,)):
    return ItemPlanRow(
        id=uuid4(), description=desc, quantity=qty, configuration_id=config,
        candidate_part_ids=tuple(candidates), selected_part_id=part,
        source_message_id=uuid4(), source_start=0, source_end=5,
    )


def _plan(rows, available=None, *, authorized=True, is_demo=False, session_id=None, generation=None, revision=1):
    return ItemPlan(
        authorized=authorized, is_demo=is_demo, session_id=session_id, session_generation=generation,
        current_revision=revision, rows=tuple(rows), available=dict(available or {}),
    )


class FakeStore:
    def __init__(self, plan=None, *, raises=None):
        self._plan = plan
        self._raises = raises

    async def load_plan(self, actor, enquiry_id):
        if self._raises is not None:
            raise self._raises
        return self._plan


class ResolveItems(unittest.IsolatedAsyncioTestCase):
    async def test_success_all_items_ready(self):
        rows = [_row(part=10, candidates=(10,)), _row(part=20, candidates=(20,))]
        store = FakeStore(_plan(rows, {10: Decimal("5"), 20: Decimal("5")}))
        result = await resolve_items(_actor(), F17Request(enquiry_id=uuid4(), expected_revision=1), store=store)
        self.assertTrue(all(i.status == "ready" for i in result.items))
        self.assertEqual(result.unresolved_item_ids, [])
        self.assertTrue(can_approve_all(result.items))

    async def test_duplicate_part_does_not_double_count_stock(self):
        a = _row(desc="line A", qty=Decimal("4"), part=10, candidates=(10,))
        b = _row(desc="line B", qty=Decimal("4"), part=10, candidates=(10,))
        store = FakeStore(_plan([a, b], {10: Decimal("5")}))  # only 5 available for both lines
        result = await resolve_items(_actor(), F17Request(enquiry_id=uuid4(), expected_revision=1), store=store)
        by_id = {i.id: i for i in result.items}
        self.assertEqual(by_id[a.id].status, "ready")        # earlier ordinal wins the stock
        self.assertEqual(by_id[b.id].status, "unavailable")  # cannot re-count the same 5 units
        self.assertIn(b.id, result.unresolved_item_ids)

    async def test_one_unresolved_item_blocks_all_items_approval(self):
        resolved = _row(part=10, candidates=(10,))
        unknown = _row(desc="mystery part", part=None, candidates=())  # no candidate -> unresolved
        store = FakeStore(_plan([resolved, unknown], {10: Decimal("5")}))
        result = await resolve_items(_actor(), F17Request(enquiry_id=uuid4(), expected_revision=1), store=store)
        self.assertIn(unknown.id, result.unresolved_item_ids)
        self.assertFalse(can_approve_all(result.items))

    async def test_needs_information_when_candidates_but_no_selection(self):
        row = _row(part=None, candidates=(10, 11))
        store = FakeStore(_plan([row], {10: Decimal("5")}))
        result = await resolve_items(_actor(), F17Request(enquiry_id=uuid4(), expected_revision=1), store=store)
        self.assertEqual(result.items[0].status, "needs_information")

    async def test_zero_quantity_rejected(self):
        store = FakeStore(_plan([_row(qty=Decimal("0"))], {10: Decimal("5")}))
        with self.assertRaises(PartsIQError) as ctx:
            await resolve_items(_actor(), F17Request(enquiry_id=uuid4(), expected_revision=1), store=store)
        self.assertEqual(ctx.exception.http_status, 422)

    async def test_more_than_twenty_items_rejected(self):
        store = FakeStore(_plan([_row(part=10 + i, candidates=(10 + i,)) for i in range(21)],
                                {10 + i: Decimal("5") for i in range(21)}))
        with self.assertRaises(PartsIQError) as ctx:
            await resolve_items(_actor(), F17Request(enquiry_id=uuid4(), expected_revision=1), store=store)
        self.assertEqual(ctx.exception.http_status, 400)

    async def test_exactly_twenty_items_tracked(self):
        rows = [_row(part=10 + i, candidates=(10 + i,)) for i in range(20)]
        store = FakeStore(_plan(rows, {10 + i: Decimal("5") for i in range(20)}))
        result = await resolve_items(_actor(), F17Request(enquiry_id=uuid4(), expected_revision=1), store=store)
        self.assertEqual(len(result.items), 20)

    async def test_unauthorized_is_not_found(self):
        store = FakeStore(_plan([_row()], {10: Decimal("5")}, authorized=False))
        with self.assertRaises(PartsIQError) as ctx:
            await resolve_items(_actor(), F17Request(enquiry_id=uuid4(), expected_revision=1), store=store)
        self.assertEqual(ctx.exception.http_status, 404)

    async def test_demo_session_mismatch_is_not_found(self):
        store = FakeStore(_plan([_row()], {10: Decimal("5")}, is_demo=True,
                                session_id=uuid4(), generation=1))
        with self.assertRaises(PartsIQError) as ctx:
            await resolve_items(_actor(session_id=uuid4(), generation=1),
                                F17Request(enquiry_id=uuid4(), expected_revision=1), store=store)
        self.assertEqual(ctx.exception.http_status, 404)

    async def test_stale_revision_rejected(self):
        store = FakeStore(_plan([_row()], {10: Decimal("5")}, revision=3))
        with self.assertRaises(PartsIQError) as ctx:
            await resolve_items(_actor(), F17Request(enquiry_id=uuid4(), expected_revision=1), store=store)
        self.assertEqual(ctx.exception.code, "STALE_REVISION")

    async def test_dependency_failure_propagates(self):
        store = FakeStore(raises=PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="db down"))
        with self.assertRaises(PartsIQError) as ctx:
            await resolve_items(_actor(), F17Request(enquiry_id=uuid4(), expected_revision=1), store=store)
        self.assertEqual(ctx.exception.code, "DEPENDENCY_UNAVAILABLE")


class HandlerReadiness(unittest.TestCase):
    def test_unresolved_items_shares_the_readiness_rule(self):
        ready = ItemState(
            id=uuid4(), request=ItemInput(description="a", quantity=Decimal("1"),
                                          source_message_id=uuid4(), source_start=0, source_end=1),
            configuration_id=100, candidate_part_ids=[10], selected_part_id=10, status="ready",
        )
        pending = ready.model_copy(update={"id": uuid4(), "status": "needs_information"})
        state = EnquiryState(
            enquiry_id=uuid4(), revision=1, session_generation=None, catalogue_version_id=uuid4(),
            items=[ready, pending], step_count=0, pending_question=None, draft_id=None,
            verification_id=None, phase="plan",
        )
        self.assertEqual(unresolved_items(state), [pending.id])


if __name__ == "__main__":
    unittest.main(verbosity=2)
