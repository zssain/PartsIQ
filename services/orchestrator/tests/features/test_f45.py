"""F45 Reply drafting — structured prose slots; code inserts every number and allocation.

Greeting/explanation/closing are generated as structured slots in the confirmed language;
code owns all facts; unapproved facts never reach prose; unsupported slots are rejected;
a provider failure permits a staff-authored controlled draft through the same gate.
"""
from __future__ import annotations

import unittest
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.rendering import render_reply
from app.specialists.reply import draft_reply, validate_slots
from partsiq_common.contracts import (
    Allocation,
    BudgetReservation,
    ReplySlots,
    VerifiedFacts,
    VerifiedItem,
)
from partsiq_common.errors import PartsIQError

WHEN = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _reservation():
    return BudgetReservation(id=uuid4(), account_id="acct", reserved_usd=Decimal("0.01"))


def _facts():
    return VerifiedFacts(
        enquiry_id=uuid4(), revision=1, catalogue_version_id=uuid4(),
        items=[
            VerifiedItem(
                item_id=uuid4(), configuration_id=100, part_id=10, part_number="VP-FF-10",
                name_en="fuel filter", name_ar="فلتر وقود", requested_quantity=Decimal("2"),
                allocations=[Allocation(warehouse_id=1, quantity=Decimal("2"), transfer_days=2, stock_updated_at=WHEN)],
                shortage=Decimal("0"), source_reference="SYNTH-CA-PB-CA-110 rev 1, section FILTERS",
                evidence_id=uuid4(),
            )
        ],
    )


class FakeOpenAI:
    def __init__(self, content):
        async def create(**kwargs):
            return SimpleNamespace(
                id="r", choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
            )

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


class FailingOpenAI:
    def __init__(self):
        async def create(**kwargs):
            raise RuntimeError("down")

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


def _json(greeting="Hello", explanation="Your request has been reviewed.", closing="Thank you."):
    return ReplySlots(greeting=greeting, explanation=explanation, closing=closing).model_dump_json()


class ReplyDrafting(unittest.IsolatedAsyncioTestCase):
    async def test_structured_slots_generated(self):  # success
        slots = await draft_reply(_facts(), "en", budget=_reservation(), client=FakeOpenAI(_json()))
        self.assertEqual((slots.greeting, slots.closing), ("Hello", "Thank you."))

    async def test_code_inserts_numbers_not_prose(self):
        facts = _facts()
        slots = await draft_reply(facts, "en", budget=_reservation(), client=FakeOpenAI(_json()))
        html = render_reply(slots, facts, "en")
        self.assertIn("VP-FF-10", html)   # fact comes from code
        self.assertNotIn("VP-FF-10", slots.explanation)  # never from prose

    async def test_locale_selects_language(self):
        facts = _facts()
        html = render_reply(ReplySlots(greeting="مرحبا", explanation="تمت المراجعة", closing="شكرا"), facts, "ar")
        self.assertIn('dir="rtl"', html)
        self.assertIn("فلتر وقود", html)

    async def test_unapproved_numeric_fact_in_prose_rejected(self):  # invalid-input
        with self.assertRaises(PartsIQError):
            await draft_reply(_facts(), "en", budget=_reservation(), client=FakeOpenAI(_json(explanation="2 units ready")))

    async def test_unsupported_slot_rejected(self):
        bad = '{"greeting":"Hi","explanation":"ok","closing":"bye","extra":"x"}'
        with self.assertRaises(PartsIQError):
            await draft_reply(_facts(), "en", budget=_reservation(), client=FakeOpenAI(bad))

    async def test_provider_failure_allows_staff_authored_draft(self):  # dependency-failure
        with self.assertRaises(PartsIQError) as ctx:
            await draft_reply(_facts(), "en", budget=_reservation(), client=FailingOpenAI())
        self.assertEqual(ctx.exception.code, "DEPENDENCY_UNAVAILABLE")
        # Staff authors controlled slots through the same gate and the renderer still works.
        staff = ReplySlots(greeting="Hello", explanation="Your selection is ready.", closing="Regards")
        validate_slots(staff)
        self.assertIn("Your selection is ready.", render_reply(staff, _facts(), "en"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
