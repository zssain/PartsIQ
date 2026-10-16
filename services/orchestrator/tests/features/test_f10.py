"""F10 Structured extraction — strict structured output; missing quantity stays a gap."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.specialists.intake import extract_intake
from partsiq_common.contracts import ActorContext, BudgetReservation, IntakeResult, ItemInput, MessageView
from partsiq_common.errors import PartsIQError

NOW = datetime(2026, 10, 17, tzinfo=timezone.utc)


class FakeOpenAI:
    def __init__(self, content: str):
        async def create(**kwargs):
            return SimpleNamespace(
                id="r", choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
            )
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


def _msg(body):
    return MessageView(id=uuid4(), enquiry_id=uuid4(), revision=1, kind="customer", body=body, created_at=NOW)


def _actor():
    return ActorContext(user_id=uuid4(), request_id=uuid4(), roles=[])


def _reservation():
    return BudgetReservation(id=uuid4(), account_id="a", reserved_usd=Decimal("0.01"))


class StructuredExtraction(unittest.IsolatedAsyncioTestCase):
    async def test_extracts_items_with_spans_and_missing_quantity(self) -> None:
        content = IntakeResult(
            language="en", preferred_locale="en", urgency="urgent",
            items=[ItemInput(description="air filter", source_message_id=uuid4(), source_start=0, source_end=10)],
        ).model_dump_json()
        result = await extract_intake([_msg("air filter")], None, _actor(), budget=_reservation(), client=FakeOpenAI(content))
        self.assertEqual(result.urgency, "urgent")
        self.assertIsNone(result.items[0].quantity)

    async def test_unsupported_output_cannot_progress(self) -> None:
        with self.assertRaises(PartsIQError):
            await extract_intake([_msg("x")], None, _actor(), budget=_reservation(), client=FakeOpenAI("{not json"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
