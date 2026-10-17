"""Intake extraction: turn customer messages into a validated IntakeResult (foundation 10).

Contract: ``async def extract_intake(context: ExtractionContext) -> IntakeResult``.

The model only PROPOSES structure (descriptions, explicitly-stated quantities, machine
hints, urgency, language) through the shared ``call_structured`` wrapper. Ordinary Python
owns every decision (CONSTRAINTS rule 2, prompt 10 steps 5-7):
  * A missing quantity stays ``null`` and becomes a clarification later — never an assumed
    order quantity.
  * The output is validated against ``IntakeResult`` (strict, extra-forbid), so status /
    approval / stock / compatibility fields or invalid quantities are rejected and cannot
    progress to search. Invalid provider JSON raises, never a silent empty result.
  * Each item's source span is re-derived IN CODE from the actual customer text, so an
    injection string in the untrusted message cannot forge a span or change the structure.
  * A confirmed machine (``confirmed_model`` / ``confirmed_serial`` supplied by the caller
    after human confirmation) is merged in and never overwritten by a re-extraction.

The structured client is injected so extraction is fully testable offline; live OpenAI is
BLOCKED unless an owner-confirmed allowance is explicitly enabled upstream.
"""
from __future__ import annotations

from typing import Any

from partsiq.ai.client import call_structured
from partsiq.ai.prompts import INTAKE_SYSTEM_PROMPT
from partsiq.core.api_models import ExtractionContext
from partsiq.core.contracts import AIRequest, IntakeResult, ItemInput, MessageView

_OUTPUT_SCHEMA = "IntakeResult"
MAX_OUTPUT_TOKENS = 2048
_DEFAULT_MODEL = "gpt-4.1-mini-2025-04-14"


def _customer_text(messages: list[MessageView]) -> str:
    """Join customer-authored message bodies with their ids so spans can be referenced."""
    return "\n".join(f"[{m.id}] {m.body}" for m in messages if m.kind == "customer")


def _source_span(messages: list[MessageView], item: ItemInput) -> ItemInput:
    """Re-derive the source span IN CODE from the customer text, not from the model.

    The model's description is located inside the first customer message that literally
    contains it; the span is the real character offset. If the description cannot be found
    verbatim (e.g. the model paraphrased), the span is pinned to the first customer message
    start so a fabricated offset from untrusted content is never trusted.
    """
    customer = [m for m in messages if m.kind == "customer"]
    for message in customer:
        start = message.body.find(item.description)
        if start >= 0:
            return item.model_copy(
                update={
                    "source_message_id": message.id,
                    "source_start": start,
                    "source_end": start + len(item.description),
                }
            )
    if customer:
        return item.model_copy(
            update={
                "source_message_id": customer[0].id,
                "source_start": 0,
                "source_end": 0,
            }
        )
    return item


def _apply_confirmed(fresh: IntakeResult, context: ExtractionContext) -> IntakeResult:
    """Merge a human-confirmed machine into the extracted items; never overwrite it.

    ``ExtractionContext`` carries at most one confirmed model/serial for the enquiry (set
    by the system after a confirmation step). It is applied to every item so a fresh
    re-extraction that left the machine blank does not lose the confirmed value, and a
    different value proposed by the model cannot silently replace the confirmed one.
    """
    if context.confirmed_model is None and context.confirmed_serial is None:
        return fresh
    merged: list[ItemInput] = []
    for item in fresh.items:
        updates: dict[str, Any] = {}
        if context.confirmed_model is not None:
            updates["model_text"] = context.confirmed_model
        if context.confirmed_serial is not None:
            updates["serial_text"] = context.confirmed_serial
        merged.append(item.model_copy(update=updates) if updates else item)
    return fresh.model_copy(update={"items": merged})


async def extract_intake(
    context: ExtractionContext,
    *,
    client: Any | None = None,
    model: str = _DEFAULT_MODEL,
    allow_live: bool = False,
) -> IntakeResult:
    """Extract a validated ``IntakeResult`` from the enquiry's customer messages.

    The customer text is passed as UNTRUSTED data; the trusted intake prompt is the only
    instruction set. The structured client is injected in tests; live OpenAI is blocked
    unless ``allow_live`` is explicitly enabled upstream.
    """
    request = AIRequest(
        request_key=context.enquiry_id,
        enquiry_id=context.enquiry_id,
        stage="intake",
        model=model,
        trusted_instructions=INTAKE_SYSTEM_PROMPT,
        untrusted_text=_customer_text(context.messages),
        image_base64=None,
        output_schema_name=_OUTPUT_SCHEMA,
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
    result = await call_structured(request, client=client, allow_live=allow_live)
    # Strict re-validation: rejects status/approval/stock fields or invalid quantities and
    # keeps a missing quantity null (the contract field is optional, never defaulted).
    fresh = IntakeResult.model_validate_json(result.output_json)
    spanned = fresh.model_copy(
        update={"items": [_source_span(context.messages, item) for item in fresh.items]}
    )
    return _apply_confirmed(spanned, context)
