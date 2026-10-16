"""Reply specialist: fill ONLY the allowed prose slots (F45).

Contract: ``async def draft_reply(facts: VerifiedFacts, locale: Locale) -> ReplySlots``.

The model writes greeting/explanation/closing as prose in the customer's confirmed
language and NOTHING else. Every number, part identifier, quantity, warehouse and
transfer estimate is inserted by code in ``app.rendering`` from the verified facts — the
model never authorizes a fact (CONSTRAINTS rule 5, ADR-007). Output is validated against
the strict ReplySlots schema (extra fields forbidden → unsupported slots rejected) and
then re-scanned here: a slot containing digits or an identifier-looking token is rejected
so the model cannot smuggle an unapproved number or part number into free prose. A
provider failure raises so the caller can fall back to a staff-authored controlled draft,
which goes through the same ``validate_slots`` gate before rendering.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from partsiq_common.ai.client import call_structured
from partsiq_common.contracts import AIRequest, BudgetReservation, Locale, ReplySlots, VerifiedFacts
from partsiq_common.errors import PartsIQError

_PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "reply.txt").read_text(encoding="utf-8")
_MODEL_ENV = "OPENAI_MODEL_TEXT"
_DEFAULT_MODEL = "gpt-4.1-mini-2025-04-14"
MAX_OUTPUT_TOKENS = 1024

# ASCII and Arabic-Indic digits — no numeric claim may live in free prose; code owns numbers.
_DIGIT = re.compile(r"[0-9٠-٩۰-۹]")
# An identifier-looking token (letters joined to digits, e.g. a part number) must not appear
# in prose either; the renderer prints identifiers in a code-owned, LTR-isolated field.
_IDENTIFIER = re.compile(r"[A-Za-z]+-?\d|\d-?[A-Za-z]")

_SLOT_NAMES = ("greeting", "explanation", "closing")


def validate_slots(slots: ReplySlots) -> None:
    """Reject prose that carries a number or identifier (F45: unapproved facts never rendered).

    ReplySlots itself (strict, extra-forbid) already rejects unsupported slots; this adds the
    content guard shared by the model draft and staff edits before either is rendered/verified.
    """
    for name in _SLOT_NAMES:
        text = getattr(slots, name)
        if _DIGIT.search(text) or _IDENTIFIER.search(text):
            raise PartsIQError(
                "VALIDATION_FAILED",
                internal_detail=f"reply slot {name!r} contains a number or identifier; facts are code-owned",
            )


def _context(facts: VerifiedFacts, locale: Locale) -> str:
    """A deliberately fact-FREE brief: the model learns intent and language, never the numbers."""
    language = "Arabic" if locale == "ar" else "English"
    outcome = "available" if any(not item.shortage for item in facts.items) else "partially available"
    return (
        f"Write the reply in {language}. The enquiry has {len(facts.items)} requested part(s); "
        f"the selection is {outcome}. Do NOT state any part number, quantity, warehouse or estimate — "
        "those are inserted separately by the system."
    )


async def draft_reply(
    facts: VerifiedFacts,
    locale: Locale,
    *,
    budget: BudgetReservation,
    client: Any | None = None,
) -> ReplySlots:
    request = AIRequest(
        request_key=facts.enquiry_id,
        enquiry_id=facts.enquiry_id,
        stage="reply",
        model=os.environ.get(_MODEL_ENV, _DEFAULT_MODEL),
        trusted_instructions=_PROMPT,
        untrusted_text=_context(facts, locale),
        output_schema_name="ReplySlots",
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
    result = await call_structured(request, budget, client=client)
    slots = ReplySlots.model_validate_json(result.output_json)  # strict; unsupported slots rejected
    validate_slots(slots)
    return slots
