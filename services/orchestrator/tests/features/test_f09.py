"""F09 Bilingual chat — Arabic/English/mixed accepted, original preserved, locale detected.

Exercises the orchestrator intake entry point (extract_intake) through the shared wrapper
with a fake provider; the customer wording is preserved verbatim and a missing quantity is
never assumed. Empty/oversized input is rejected by the strict contract.
"""
from __future__ import annotations

import unittest
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.specialists.intake import extract_intake
from partsiq_common.contracts import ActorContext, BudgetReservation, IntakeResult, ItemInput, MessageView
from partsiq_common.errors import PartsIQError

NOW = datetime(2026, 10, 17, tzinfo=UTC)


def _reservation():
    return BudgetReservation(id=uuid4(), account_id="acct", reserved_usd=Decimal("0.01"))


def _actor():
    return ActorContext(user_id=uuid4(), request_id=uuid4(), roles=[])


def _message(body):
    return MessageView(id=uuid4(), enquiry_id=uuid4(), revision=1, kind="customer", body=body, created_at=NOW)


class FakeOpenAI:
    def __init__(self, content):
        async def create(**kwargs):
            return SimpleNamespace(
                id="r", choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
            )

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


class BilingualChat(unittest.IsolatedAsyncioTestCase):
    async def test_mixed_language_preserved_and_locale_detected(self):
        payload = IntakeResult(
            language="mixed", preferred_locale="ar", urgency="normal",
            items=[
                ItemInput(description="فلتر زيت oil filter", quantity=Decimal("2"),
                          source_message_id=uuid4(), source_start=0, source_end=5),
            ],
        ).model_dump_json()
        result = await extract_intake([_message("فلتر زيت oil filter x2")], None, _actor(),
                                      budget=_reservation(), client=FakeOpenAI(payload))
        self.assertEqual(result.language, "mixed")
        self.assertEqual(result.preferred_locale, "ar")
        self.assertIn("فلتر", result.items[0].description)  # original wording preserved verbatim

    async def test_missing_quantity_not_assumed(self):
        payload = IntakeResult(
            language="en", preferred_locale="en", urgency="normal",
            items=[ItemInput(description="fuel filter", source_message_id=uuid4(), source_start=0, source_end=11)],
        ).model_dump_json()
        result = await extract_intake([_message("fuel filter")], None, _actor(),
                                      budget=_reservation(), client=FakeOpenAI(payload))
        self.assertIsNone(result.items[0].quantity)

    async def test_oversized_input_rejected_by_contract(self):  # invalid-input
        bad = '{"language":"en","preferred_locale":"en","urgency":"normal","items":[' \
              '{"description":"%s","source_message_id":"%s","source_start":0,"source_end":1}]}' % ("x" * 1001, uuid4())
        with self.assertRaises(PartsIQError):
            await extract_intake([_message("x")], None, _actor(), budget=_reservation(), client=FakeOpenAI(bad))


if __name__ == "__main__":
    unittest.main(verbosity=2)
