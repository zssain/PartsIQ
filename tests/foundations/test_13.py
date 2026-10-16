"""Acceptance tests for prompt 13 — reply specialist and renderer (foundation gate).

Offline: a fake OpenAI client feeds canned ReplySlots through the real shared wrapper, so
slot generation, the no-facts-in-prose guard, unsupported-slot rejection and the
provider-failure staff path are exercised without a provider. The renderer is pure: it
inserts every fact in code, HTML-escapes all text, renders Arabic RTL with LTR-isolated
identifiers, and never emits a price. Covers F45.
"""
from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "partsiq_common"))
sys.path.insert(0, str(REPO_ROOT / "services" / "orchestrator"))

from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

from app.graph import build_graph  # noqa: E402
from app.handlers import WorkflowHandlers, make_draft_handler  # noqa: E402
from app.rendering import render_reply  # noqa: E402
from app.specialists.reply import draft_reply, validate_slots  # noqa: E402
from partsiq_common.contracts import (  # noqa: E402
    Allocation,
    BudgetReservation,
    EnquiryState,
    ReplySlots,
    VerifiedFacts,
    VerifiedItem,
)
from partsiq_common.errors import PartsIQError  # noqa: E402

WHEN = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
CV = uuid4()


def _reservation():
    return BudgetReservation(id=uuid4(), account_id="acct", reserved_usd=Decimal("0.01"))


def _facts(*, shortage="0", name_en="fuel filter", name_ar="فلتر وقود"):
    return VerifiedFacts(
        enquiry_id=uuid4(), revision=1, catalogue_version_id=CV,
        items=[
            VerifiedItem(
                item_id=uuid4(), configuration_id=100, part_id=10, part_number="VP-FF-10",
                name_en=name_en, name_ar=name_ar, requested_quantity=Decimal("2"),
                allocations=[Allocation(warehouse_id=1, quantity=Decimal("2"), transfer_days=2, stock_updated_at=WHEN)],
                shortage=Decimal(shortage), source_reference="SYNTH-CA-PB-CA-110 rev 1, section FILTERS",
                evidence_id=uuid4(),
            )
        ],
    )


class FakeOpenAI:
    def __init__(self, content: str):
        async def create(**kwargs):
            return SimpleNamespace(
                id="resp-1",
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                usage=SimpleNamespace(prompt_tokens=5, completion_tokens=5),
            )

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


class FailingOpenAI:
    def __init__(self):
        async def create(**kwargs):
            raise RuntimeError("provider down")

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


def _slots_json(greeting="Hello", explanation="Your request has been reviewed.", closing="Thank you."):
    return ReplySlots(greeting=greeting, explanation=explanation, closing=closing).model_dump_json()


class DraftReply(unittest.IsolatedAsyncioTestCase):
    async def test_generates_structured_slots(self):  # F45 success
        slots = await draft_reply(_facts(), "en", budget=_reservation(), client=FakeOpenAI(_slots_json()))
        self.assertIsInstance(slots, ReplySlots)
        self.assertEqual(slots.greeting, "Hello")

    async def test_numeric_claim_in_prose_is_rejected(self):  # unapproved facts never in prose
        bad = _slots_json(explanation="We found 3 parts in stock.")
        with self.assertRaises(PartsIQError) as ctx:
            await draft_reply(_facts(), "en", budget=_reservation(), client=FakeOpenAI(bad))
        self.assertEqual(ctx.exception.code, "VALIDATION_FAILED")

    async def test_identifier_in_prose_is_rejected(self):
        bad = _slots_json(explanation="Part VP-10 is ready.")
        with self.assertRaises(PartsIQError):
            await draft_reply(_facts(), "en", budget=_reservation(), client=FakeOpenAI(bad))

    async def test_unsupported_slot_is_rejected(self):  # strict schema
        bad = '{"greeting":"Hi","explanation":"ok","closing":"bye","status":"approved"}'
        with self.assertRaises(PartsIQError):
            await draft_reply(_facts(), "en", budget=_reservation(), client=FakeOpenAI(bad))

    async def test_provider_failure_raises_for_staff_fallback(self):  # dependency-failure
        with self.assertRaises(PartsIQError) as ctx:
            await draft_reply(_facts(), "en", budget=_reservation(), client=FailingOpenAI())
        self.assertEqual(ctx.exception.code, "DEPENDENCY_UNAVAILABLE")


class ValidateSlots(unittest.TestCase):
    def test_clean_prose_passes(self):
        validate_slots(ReplySlots(greeting="Hello", explanation="All set for review.", closing="Regards"))

    def test_arabic_indic_digit_rejected(self):
        with self.assertRaises(PartsIQError):
            validate_slots(ReplySlots(greeting="مرحبا", explanation="لديك ٣ قطع", closing="شكرا"))


class RenderReply(unittest.TestCase):
    def test_inserts_facts_in_code(self):
        facts = _facts()
        slots = ReplySlots(greeting="Hello", explanation="Reviewed.", closing="Thanks")
        html = render_reply(slots, facts, "en")
        self.assertIn("VP-FF-10", html)      # identifier inserted by code
        self.assertIn("fuel filter", html)   # localized name
        self.assertIn("Qty", html)
        self.assertIn("Warehouse", html)
        self.assertIn("estimated transfer", html)
        self.assertIn("not guaranteed", html)

    def test_no_price_or_quotation_wording(self):
        html = render_reply(ReplySlots(greeting="Hi", explanation="ok", closing="bye"), _facts(), "en").lower()
        for banned in ("price", "quotation", "$", "sar", "usd"):
            self.assertNotIn(banned, html)

    def test_arabic_is_rtl_and_uses_arabic_name(self):
        html = render_reply(ReplySlots(greeting="مرحبا", explanation="تمت المراجعة", closing="شكرا"), _facts(), "ar")
        self.assertIn('dir="rtl"', html)
        self.assertIn("فلتر وقود", html)      # Arabic name chosen
        self.assertIn('<bdi dir="ltr">VP-FF-10</bdi>', html)  # identifier isolated LTR

    def test_html_is_escaped(self):  # F27: user/catalogue HTML is escaped
        facts = _facts(name_en='<script>alert(1)</script>')
        html = render_reply(ReplySlots(greeting="Hi", explanation="ok", closing="bye"), facts, "en")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_shortage_rendered_when_present(self):
        facts = _facts(shortage="1")
        html = render_reply(ReplySlots(greeting="Hi", explanation="ok", closing="bye"), facts, "en")
        self.assertIn("Awaiting stock", html)

    def test_staff_authored_slots_render_without_provider(self):  # F45 staff fallback path
        staff = ReplySlots(greeting="Hello", explanation="Your selection is ready for review.", closing="Regards")
        validate_slots(staff)  # same gate as the model draft
        html = render_reply(staff, _facts(), "en")
        self.assertIn("Your selection is ready for review.", html)


class FakeDraftStore:
    def __init__(self, loaded):
        self._loaded = loaded
        self.saved = None

    async def load_facts(self, enquiry_id, revision):
        return self._loaded

    async def persist_draft(self, enquiry_id, revision, locale, slots, facts, rendered_text):
        self.saved = rendered_text
        return uuid4()


class GraphWiring(unittest.IsolatedAsyncioTestCase):
    async def test_draft_handler_persists_and_sets_phase(self):
        facts = _facts()
        store = FakeDraftStore((facts, "en"))
        draft = make_draft_handler(store, budget=_reservation(), client=FakeOpenAI(_slots_json()))
        state = EnquiryState(
            enquiry_id=facts.enquiry_id, revision=1, session_generation=None, catalogue_version_id=CV,
            items=[], step_count=0, pending_question=None, draft_id=None, verification_id=None, phase="planned",
        )
        updated = await draft(state)
        self.assertIsNotNone(updated.draft_id)
        self.assertEqual(updated.phase, "drafted")
        self.assertIn("VP-FF-10", store.saved)

    async def test_draft_handler_provider_failure_routes_to_staff(self):
        facts = _facts()
        store = FakeDraftStore((facts, "en"))
        draft = make_draft_handler(store, budget=_reservation(), client=FailingOpenAI())
        state = EnquiryState(
            enquiry_id=facts.enquiry_id, revision=1, session_generation=None, catalogue_version_id=CV,
            items=[], step_count=0, pending_question=None, draft_id=None, verification_id=None, phase="planned",
        )
        updated = await draft(state)
        self.assertIsNone(updated.draft_id)
        self.assertEqual(updated.phase, "needs_staff_draft")

    async def test_build_graph_accepts_draft_handler(self):
        store = FakeDraftStore((_facts(), "en"))

        async def passthrough(s):
            return s

        handlers = WorkflowHandlers(
            intake=passthrough, identify=passthrough, search=passthrough, choose=passthrough,
            plan=passthrough, draft=make_draft_handler(store, budget=_reservation(), client=FakeOpenAI(_slots_json())),
            verify=passthrough,
        )
        self.assertIsNotNone(build_graph(handlers, InMemorySaver()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
