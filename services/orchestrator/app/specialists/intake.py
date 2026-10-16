"""Intake specialist: turn customer messages into a validated IntakeResult.

Contract: ``async def extract_intake(messages, previous, actor) -> IntakeResult``.

The model only PROPOSES structure (descriptions, explicitly-stated quantities, machine
hints, urgency, language) via the shared structured-output wrapper. Code owns the rest:
  * A missing quantity stays null and becomes a clarification later — never an assumed
    order quantity (F10).
  * The output is validated against IntakeResult (strict, extra-forbid), so status /
    approval / stock / compatibility fields or invalid quantities are rejected and cannot
    progress to search.
  * A previously CONFIRMED machine field is not silently overwritten by a re-extraction.

The OpenAI client and budget reservation are injected so extraction is testable offline.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from partsiq_common.ai.client import call_structured
from partsiq_common.contracts import AIRequest, ActorContext, BudgetReservation, IntakeResult, MessageView

_PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "intake.txt").read_text(encoding="utf-8")
_MODEL_ENV = "OPENAI_MODEL_TEXT"
_DEFAULT_MODEL = "gpt-4.1-mini-2025-04-14"
MAX_OUTPUT_TOKENS = 2048


def _customer_text(messages: list[MessageView]) -> str:
    """Join customer-authored messages with their ids so spans can be referenced."""
    parts = [f"[{m.id}] {m.body}" for m in messages if m.kind == "customer"]
    return "\n".join(parts)


def _merge_confirmed(fresh: IntakeResult, previous: IntakeResult | None) -> IntakeResult:
    """Carry forward confirmed machine fields the re-extraction left blank (don't lose them)."""
    if previous is None:
        return fresh
    merged_items = []
    for index, item in enumerate(fresh.items):
        if index < len(previous.items):
            prior = previous.items[index]
            updates: dict[str, Any] = {}
            if item.model_text is None and prior.model_text is not None:
                updates["model_text"] = prior.model_text
            if item.serial_text is None and prior.serial_text is not None:
                updates["serial_text"] = prior.serial_text
            if updates:
                item = item.model_copy(update=updates)
        merged_items.append(item)
    return fresh.model_copy(update={"items": merged_items})


async def extract_intake(
    messages: list[MessageView],
    previous: IntakeResult | None,
    actor: ActorContext,
    *,
    budget: BudgetReservation,
    client: Any | None = None,
) -> IntakeResult:
    request = AIRequest(
        request_key=actor.request_id,
        enquiry_id=None,
        stage="intake",
        model=os.environ.get(_MODEL_ENV, _DEFAULT_MODEL),
        trusted_instructions=_PROMPT,
        untrusted_text=_customer_text(messages),
        output_schema_name="IntakeResult",
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
    result = await call_structured(request, budget, client=client)
    fresh = IntakeResult.model_validate_json(result.output_json)  # strict; rejects bad fields/quantities
    return _merge_confirmed(fresh, previous)
