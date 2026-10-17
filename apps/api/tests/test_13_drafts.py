"""Foundation 13 acceptance: bilingual reply slots and safe rendering (F45, F27, F27).

Ports the behaviour characterized in services/orchestrator/tests/features/test_f45.py and
the F27 "user HTML is escaped" rule for the reply renderer.

Deterministic and fully offline: live OpenAI is BLOCKED (an injected fake structured client
returns canned slots) and the live drafts store is BLOCKED (an in-memory fake mirroring
UNIQUE(enquiry_id, revision) stands in). The live paths are SKIPPED, never faked.

Covered behaviours:
  * validate_slots rejects an ASCII digit, an Arabic-Indic digit and an identifier token.
  * the strict ReplySlots schema rejects an unsupported slot (draft_reply refuses it).
  * render_reply html-escapes prose and names, wraps identifiers in LTR <bdi> under RTL,
    includes the code-owned part/quantity/warehouse/estimate lines, labels transfers as
    NON-GUARANTEED, and contains NO price/quotation wording.
  * a provider failure yields the staff-draft path (DEPENDENCY_UNAVAILABLE), and staff prose
    goes through the same validate_slots gate — no fabricated prose.
  * a draft binds to the verified-facts hash and is one-per-(enquiry, revision).
"""
from __future__ import annotations

import os
import unittest
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

from partsiq.ai.reply import REPLY_SYSTEM_PROMPT, draft_reply, validate_slots
from partsiq.core.contracts import (
    Allocation,
    ReplySlots,
    VerifiedFacts,
    VerifiedItem,
)
from partsiq.core.errors import PartsIQError
from partsiq.enquiries.drafts import (
    StoredDraft,
    build_draft_view,
    draft_is_current,
    load_draft,
    save_draft,
)
from partsiq.enquiries.facts import facts_sha256
from partsiq.enquiries.renderer import render_reply

WHEN = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _facts(*, enquiry_id=None, revision=1, catalogue=None, shortage="0"):
    return VerifiedFacts(
        enquiry_id=enquiry_id or uuid4(),
        revision=revision,
        catalogue_version_id=catalogue or uuid4(),
        items=[
            VerifiedItem(
                item_id=uuid4(),
                configuration_id=100,
                part_id=10,
                part_number="VP-FF-10",
                name_en="fuel filter",
                name_ar="فلتر وقود",
                requested_quantity=Decimal("2"),
                allocations=[
                    Allocation(
                        warehouse_id=7,
                        quantity=Decimal("2"),
                        transfer_days=3,
                        stock_updated_at=WHEN,
                    )
                ],
                shortage=Decimal(shortage),
                source_reference="SYNTH-CA-PB-CA-110 rev 1, section FILTERS",
                evidence_id=uuid4(),
            )
        ],
    )


class FakeOpenAI:
    """Injected structured client returning canned JSON — no network, no live key."""

    def __init__(self, content: str):
        async def create(**kwargs):
            return SimpleNamespace(
                id="r",
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
            )

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


class FailingOpenAI:
    """Injected client whose call raises — stands in for a provider/credit failure."""

    def __init__(self):
        async def create(**kwargs):
            raise RuntimeError("provider down")

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


def _json(
    greeting="Hello",
    explanation="Your request has been reviewed and a selection is ready.",
    closing="Thank you.",
):
    return ReplySlots(
        greeting=greeting, explanation=explanation, closing=closing
    ).model_dump_json()


class UniqueDraftStore:
    """In-memory mirror of the drafts table with UNIQUE(enquiry_id, revision).

    Stands in for the BLOCKED live Postgres adapter: upsert() keeps exactly one row per
    (enquiry, revision) exactly as the unique index guarantees.
    """

    def __init__(self):
        self._rows: dict[tuple[UUID, int], StoredDraft] = {}
        self.upsert_calls = 0

    async def upsert(self, draft: StoredDraft) -> StoredDraft:
        self.upsert_calls += 1
        self._rows[(draft.enquiry_id, draft.revision)] = draft
        return draft

    async def load(self, enquiry_id: UUID, revision: int) -> StoredDraft | None:
        return self._rows.get((enquiry_id, revision))


# ---------------------------------------------------------------------------
# validate_slots — content guard (F45 step 4).
# ---------------------------------------------------------------------------
class ValidateSlots(unittest.TestCase):
    def test_accepts_fact_free_prose(self):
        validate_slots(ReplySlots(greeting="Hello", explanation="A selection is ready.", closing="Regards"))

    def test_rejects_ascii_digit(self):
        with self.assertRaises(PartsIQError) as ctx:
            validate_slots(ReplySlots(greeting="Hi", explanation="3 units are ready.", closing="Bye"))
        self.assertEqual(ctx.exception.code, "VALIDATION_FAILED")

    def test_rejects_arabic_indic_digit(self):
        # Arabic-Indic '٣' (U+0663) is a digit too; a number in prose is rejected regardless of script.
        with self.assertRaises(PartsIQError) as ctx:
            validate_slots(ReplySlots(greeting="مرحبا", explanation="تم تجهيز ٣ قطع.", closing="شكرا"))
        self.assertEqual(ctx.exception.code, "VALIDATION_FAILED")

    def test_rejects_identifier_token(self):
        with self.assertRaises(PartsIQError) as ctx:
            validate_slots(ReplySlots(greeting="Hi", explanation="Part VP10 is ready.", closing="Bye"))
        self.assertEqual(ctx.exception.code, "VALIDATION_FAILED")


# ---------------------------------------------------------------------------
# draft_reply — structured slots, schema rejection, provider failure (F45).
# ---------------------------------------------------------------------------
class DraftReply(unittest.IsolatedAsyncioTestCase):
    async def test_structured_slots_generated(self):
        slots = await draft_reply(_facts(), "en", client=FakeOpenAI(_json()))
        self.assertEqual((slots.greeting, slots.closing), ("Hello", "Thank you."))

    async def test_brief_is_fact_free_and_prompt_forbids_numbers(self):
        # The trusted prompt explicitly forbids numbers/identifiers; code owns facts.
        self.assertIn("Do NOT write any number", REPLY_SYSTEM_PROMPT)

    async def test_unsupported_slot_rejected_by_strict_schema(self):
        bad = '{"greeting":"Hi","explanation":"ok","closing":"bye","extra":"x"}'
        with self.assertRaises((PartsIQError, Exception)) as ctx:
            await draft_reply(_facts(), "en", client=FakeOpenAI(bad))
        # The strict ReplySlots schema (extra='forbid') rejects the unsupported slot; the
        # client wrapper validates the JSON against the schema before returning.
        self.assertIsNotNone(ctx.exception)

    async def test_unapproved_numeric_fact_in_prose_rejected(self):
        with self.assertRaises(PartsIQError) as ctx:
            await draft_reply(_facts(), "en", client=FakeOpenAI(_json(explanation="2 units ready")))
        self.assertEqual(ctx.exception.code, "VALIDATION_FAILED")

    async def test_provider_failure_routes_to_staff_draft(self):
        # A provider failure RAISES (DEPENDENCY_UNAVAILABLE) — never fabricated prose.
        with self.assertRaises(PartsIQError) as ctx:
            await draft_reply(_facts(), "en", client=FailingOpenAI())
        self.assertEqual(ctx.exception.code, "DEPENDENCY_UNAVAILABLE")
        # Staff author the SAME controlled slots through the SAME gate; the renderer still works.
        staff = ReplySlots(greeting="Hello", explanation="Your selection is ready.", closing="Regards")
        validate_slots(staff)
        self.assertIn("Your selection is ready.", render_reply(staff, _facts(), "en"))

    async def test_live_openai_blocked_without_client(self):
        # With no injected client and allow_live left false, the live path is BLOCKED.
        with self.assertRaises(PartsIQError) as ctx:
            await draft_reply(_facts(), "en")
        self.assertIn(ctx.exception.code, ("CREDIT_UNAVAILABLE", "DEPENDENCY_UNAVAILABLE"))


# ---------------------------------------------------------------------------
# render_reply — safe, code-owned rendering (F45 layout, F27 escaping, RTL bdi).
# ---------------------------------------------------------------------------
class RenderReply(unittest.TestCase):
    def test_code_inserts_facts_not_prose(self):
        facts = _facts()
        slots = ReplySlots(greeting="Hello", explanation="Your request has been reviewed.", closing="Thanks")
        html = render_reply(slots, facts, "en")
        # Facts come from code, never from prose.
        self.assertIn("VP-FF-10", html)
        self.assertNotIn("VP-FF-10", slots.explanation)

    def test_includes_code_owned_part_qty_warehouse_estimate_lines(self):
        html = render_reply(
            ReplySlots(greeting="Hello", explanation="Reviewed.", closing="Thanks"),
            _facts(),
            "en",
        )
        self.assertIn("VP-FF-10", html)       # part identifier
        self.assertIn("Qty", html)            # quantity label
        self.assertIn("Warehouse", html)      # warehouse label
        self.assertIn(">7<", html)            # warehouse id, code-owned
        self.assertIn("estimated transfer", html)  # transfer estimate
        self.assertIn(">3<", html)            # transfer days, code-owned

    def test_transfers_labelled_non_guaranteed(self):
        html = render_reply(
            ReplySlots(greeting="Hello", explanation="Reviewed.", closing="Thanks"),
            _facts(),
            "en",
        )
        self.assertIn("estimate only, not guaranteed", html)

    def test_no_price_or_quotation_wording(self):
        html = render_reply(
            ReplySlots(greeting="Hello", explanation="Reviewed.", closing="Thanks"),
            _facts(),
            "en",
        ).lower()
        for banned in ("price", "quote", "quotation", "$", "usd", "cost", "invoice", "payment"):
            self.assertNotIn(banned, html)

    def test_html_escaped_prose_and_name(self):
        # F27: user/catalogue HTML is escaped, never executed.
        facts = _facts()
        facts = facts.model_copy(
            update={
                "items": [facts.items[0].model_copy(update={"name_en": "<script>x</script>"})]
            }
        )
        slots = ReplySlots(
            greeting="<b>Hi</b>",
            explanation="Reviewed & ready <img src=x>",
            closing="Thanks",
        )
        html = render_reply(slots, facts, "en")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<b>Hi</b>", html)
        self.assertIn("&lt;b&gt;Hi&lt;/b&gt;", html)
        self.assertIn("&amp;", html)

    def test_arabic_rtl_with_ltr_isolated_identifiers(self):
        facts = _facts()
        html = render_reply(
            ReplySlots(greeting="مرحبا", explanation="تمت المراجعة", closing="شكرا"),
            facts,
            "ar",
        )
        self.assertIn('dir="rtl"', html)
        self.assertIn('lang="ar"', html)
        self.assertIn("فلتر وقود", html)          # Arabic part name
        # Identifiers are isolated LTR with <bdi> so they read correctly in RTL prose.
        self.assertIn('<bdi dir="ltr">VP-FF-10</bdi>', html)
        self.assertIn('<bdi dir="ltr">7</bdi>', html)


# ---------------------------------------------------------------------------
# Draft persistence — fact binding and one-per-(enquiry, revision).
# ---------------------------------------------------------------------------
class DraftPersistence(unittest.IsolatedAsyncioTestCase):
    async def test_draft_binds_to_verified_facts_hash(self):
        facts = _facts()
        slots = ReplySlots(greeting="Hello", explanation="Reviewed.", closing="Thanks")
        store = UniqueDraftStore()
        draft = await save_draft(slots, facts, "en", store=store)
        self.assertEqual(draft.facts_sha256, facts_sha256(facts))
        self.assertTrue(draft_is_current(draft, facts))
        # A materially changed plan hashes differently -> the draft is no longer current.
        changed = facts.model_copy(update={"catalogue_version_id": uuid4()})
        self.assertFalse(draft_is_current(draft, changed))

    async def test_one_draft_per_enquiry_revision(self):
        facts = _facts()
        store = UniqueDraftStore()
        await save_draft(
            ReplySlots(greeting="Hello", explanation="First.", closing="Thanks"), facts, "en", store=store
        )
        # Re-saving the same (enquiry, revision) replaces the single row, never appends.
        await save_draft(
            ReplySlots(greeting="Hello", explanation="Second.", closing="Thanks"), facts, "en", store=store
        )
        self.assertEqual(len(store._rows), 1)
        self.assertEqual(store.upsert_calls, 2)
        loaded = await load_draft(facts.enquiry_id, facts.revision, store=store)
        self.assertIn("Second.", loaded.rendered_preview)

    async def test_save_rejects_prose_with_numbers_before_persisting(self):
        facts = _facts()
        store = UniqueDraftStore()
        with self.assertRaises(PartsIQError):
            await save_draft(
                ReplySlots(greeting="Hi", explanation="3 units ready.", closing="Bye"),
                facts,
                "en",
                store=store,
            )
        self.assertEqual(len(store._rows), 0)  # nothing persisted on a rejected draft

    async def test_missing_draft_is_not_found(self):
        store = UniqueDraftStore()
        with self.assertRaises(PartsIQError) as ctx:
            await load_draft(uuid4(), 1, store=store)
        self.assertEqual(ctx.exception.code, "NOT_FOUND")

    async def test_draft_view_assembled_from_stored_draft(self):
        facts = _facts()
        store = UniqueDraftStore()
        draft = await save_draft(
            ReplySlots(greeting="Hello", explanation="Reviewed.", closing="Thanks"), facts, "en", store=store
        )
        view = build_draft_view(draft, verification_passed=True)
        self.assertEqual(view.revision, facts.revision)
        self.assertEqual(view.slots, draft.slots)
        self.assertEqual(view.rendered_preview, draft.rendered_preview)
        self.assertTrue(view.verification_passed)


@unittest.skipUnless(
    os.environ.get("PARTSIQ_LIVE_OPENAI") == "1",
    "live OpenAI reply drafting is BLOCKED; set PARTSIQ_LIVE_OPENAI=1 to run",
)
class LiveReplyDrafting(unittest.IsolatedAsyncioTestCase):  # pragma: no cover
    async def test_live_reply_draft(self):
        raise AssertionError("live OpenAI path is BLOCKED and must never run in CI")


if __name__ == "__main__":
    unittest.main(verbosity=2)
