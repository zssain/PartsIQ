"""Acceptance tests for prompt 10 — intake specialist.

Offline: a fake OpenAI client feeds canned structured output through the real shared
wrapper, so extraction, strict-schema rejection and confirmed-field merge are exercised
without a provider. Live OpenAI is integration-only. Covers F09, F10.
"""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "partsiq_common"))
sys.path.insert(0, str(REPO_ROOT / "services" / "orchestrator"))

from app.specialists.intake import extract_intake  # noqa: E402
from partsiq_common.contracts import (  # noqa: E402
    ActorContext,
    BudgetReservation,
    IntakeResult,
    ItemInput,
    MessageView,
)
from partsiq_common.errors import PartsIQError  # noqa: E402

NOW = datetime(2026, 10, 17, tzinfo=timezone.utc)


def _reservation():
    return BudgetReservation(id=uuid4(), account_id="acct", reserved_usd=Decimal("0.01"))


def _actor():
    return ActorContext(user_id=uuid4(), request_id=uuid4(), roles=[])


def _message(body, kind="customer"):
    return MessageView(id=uuid4(), enquiry_id=uuid4(), revision=1, kind=kind, body=body, created_at=NOW)


class FakeOpenAI:
    """Returns a fixed structured-output JSON string as the model response."""

    def __init__(self, content: str):
        async def create(**kwargs):
            return SimpleNamespace(
                id="resp-1",
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                usage=SimpleNamespace(prompt_tokens=5, completion_tokens=5),
            )

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


def _valid_intake_json():
    return IntakeResult(
        language="mixed",
        preferred_locale="ar",
        urgency="normal",
        items=[
            ItemInput(description="فلتر زيت", quantity=Decimal("2"), model_text="VP-20",
                      source_message_id=uuid4(), source_start=0, source_end=5),
            ItemInput(description="fuel filter", quantity=None,
                      source_message_id=uuid4(), source_start=6, source_end=17),
        ],
    ).model_dump_json()


class IntakeExtraction(unittest.IsolatedAsyncioTestCase):
    async def test_success_preserves_missing_quantity_and_language(self) -> None:
        client = FakeOpenAI(_valid_intake_json())
        result = await extract_intake([_message("...")], None, _actor(), budget=_reservation(), client=client)
        self.assertEqual(result.language, "mixed")   # F09 bilingual preserved
        self.assertEqual(len(result.items), 2)
        self.assertEqual(result.items[0].quantity, Decimal("2"))
        self.assertIsNone(result.items[1].quantity)   # F10: missing quantity NOT assumed

    async def test_invalid_quantity_is_rejected(self) -> None:
        bad = '{"language":"en","preferred_locale":"en","urgency":"normal","items":[' \
              '{"description":"x","quantity":"0","source_message_id":"%s","source_start":0,"source_end":1}]}' % uuid4()
        with self.assertRaises(PartsIQError):
            await extract_intake([_message("x")], None, _actor(), budget=_reservation(), client=FakeOpenAI(bad))

    async def test_disallowed_field_is_rejected(self) -> None:
        bad = '{"language":"en","preferred_locale":"en","urgency":"normal","status":"approved","items":[' \
              '{"description":"x","source_message_id":"%s","source_start":0,"source_end":1}]}' % uuid4()
        with self.assertRaises(PartsIQError):
            await extract_intake([_message("x")], None, _actor(), budget=_reservation(), client=FakeOpenAI(bad))

    async def test_confirmed_machine_not_overwritten(self) -> None:
        previous = IntakeResult(
            language="en", preferred_locale="en", urgency="normal",
            items=[ItemInput(description="oil filter", model_text="VP-20", serial_text="150000",
                             source_message_id=uuid4(), source_start=0, source_end=3)],
        )
        fresh_json = IntakeResult(
            language="en", preferred_locale="en", urgency="normal",
            items=[ItemInput(description="oil filter", source_message_id=uuid4(), source_start=0, source_end=3)],
        ).model_dump_json()
        result = await extract_intake(
            [_message("oil filter")], previous, _actor(), budget=_reservation(), client=FakeOpenAI(fresh_json)
        )
        self.assertEqual(result.items[0].model_text, "VP-20")   # carried forward
        self.assertEqual(result.items[0].serial_text, "150000")

    async def test_only_customer_messages_are_sent(self) -> None:
        from app.specialists.intake import _customer_text
        text = _customer_text([_message("hello", kind="customer"), _message("status", kind="status")])
        self.assertIn("hello", text)
        self.assertNotIn("status", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
