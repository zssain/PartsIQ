"""Language providers for intake extraction and reply prose (fixture vs live), ADR 0002.

Exactly one provider is chosen per RUN when it starts (``execution_source``) and it never
changes while the run is active: a live run that loses its provider or allowance BLOCKS with an
explicit reason instead of silently continuing on fixture output. Fixture replay is offered to
the user as a separate, clearly labelled run.

* :class:`FixtureLanguage` — rule-based extraction over the catalogue vocabulary and code-owned
  reply prose. Makes no network call and spends nothing.
* :class:`LiveLanguage` — the existing structured OpenAI path (:mod:`partsiq.ai.extraction`,
  :mod:`partsiq.ai.reply`) behind the owner's confirmed allowance. Every call reserves the
  worst-case cost from the run's budget first; an unknown price, an expired allowance or an
  exhausted cap raises ``CREDIT_UNAVAILABLE``. There is no paid fallback.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Protocol

from partsiq.core.contracts import Locale, ReplySlots, VerifiedFacts
from partsiq.core.errors import PartsIQError

from .catalogue import CatalogueContext
from .domain import ExtractedItem, IntakeOutcome, fixture_extract, fixture_slots


@dataclass
class CallUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_usd: Decimal = Decimal("0")


class LanguageProvider(Protocol):
    source: str

    async def extract(self, text: str, catalogue: CatalogueContext, *, enquiry_id: Any) -> tuple[IntakeOutcome, CallUsage]: ...

    async def draft(self, facts: VerifiedFacts, locale: Locale) -> tuple[ReplySlots, CallUsage]: ...


class FixtureLanguage:
    source = "fixture"

    async def extract(self, text: str, catalogue: CatalogueContext, *, enquiry_id: Any) -> tuple[IntakeOutcome, CallUsage]:
        return fixture_extract(text, catalogue), CallUsage()

    async def draft(self, facts: VerifiedFacts, locale: Locale) -> tuple[ReplySlots, CallUsage]:
        return fixture_slots(locale, facts), CallUsage()


class Allowance(Protocol):
    """Run-scoped budget gate (implemented by :class:`partsiq.workspace.limits.RunBudget`)."""

    async def reserve(self, stage: str, max_output_tokens: int) -> Any: ...

    async def settle(self, reservation: Any, input_tokens: int, output_tokens: int) -> Decimal: ...


class LiveLanguage:
    """OpenAI-backed extraction and prose through the existing wrapped client (no tools sent)."""

    source = "live"

    def __init__(self, *, client: Any, text_model: str, allowance: Allowance) -> None:
        self._client = client
        self._model = text_model
        self._allowance = allowance

    async def extract(self, text: str, catalogue: CatalogueContext, *, enquiry_id: Any) -> tuple[IntakeOutcome, CallUsage]:
        from partsiq.ai.client import call_structured
        from partsiq.ai.prompts import INTAKE_SYSTEM_PROMPT
        from partsiq.core.contracts import AIRequest, IntakeResult

        reservation = await self._allowance.reserve("intake", 800)
        request = AIRequest(
            request_key=enquiry_id,
            enquiry_id=enquiry_id,
            stage="intake",
            model=self._model,
            trusted_instructions=INTAKE_SYSTEM_PROMPT,
            untrusted_text=text[:12000],
            image_base64=None,
            output_schema_name="IntakeResult",
            max_output_tokens=800,
        )
        result = await call_structured(request, client=self._client, allow_live=True)
        cost = await self._allowance.settle(reservation, result.input_tokens, result.output_tokens)
        parsed = IntakeResult.model_validate_json(result.output_json)
        # The model proposes structure only; quoted part numbers and the configuration code are
        # still read by code from the customer's own text so the model cannot inject identifiers.
        coded = fixture_extract(text, catalogue)
        items = [
            ExtractedItem(
                description=item.description,
                quantity=item.quantity,
                model_text=item.model_text,
                serial_text=item.serial_text,
                config_code_text=coded.items[0].config_code_text if coded.items else None,
                part_numbers=coded.items[0].part_numbers if (coded.items and len(parsed.items) == 1) else [],
            )
            for item in parsed.items
        ]
        outcome = IntakeOutcome(language=parsed.language, urgency=parsed.urgency, items=items, source="live")
        return outcome, CallUsage(result.input_tokens, result.output_tokens, cost)

    async def draft(self, facts: VerifiedFacts, locale: Locale) -> tuple[ReplySlots, CallUsage]:
        from partsiq.ai.reply import MAX_OUTPUT_TOKENS, REPLY_SYSTEM_PROMPT, _context, validate_slots
        from partsiq.ai.client import call_structured
        from partsiq.core.contracts import AIRequest

        reservation = await self._allowance.reserve("reply", MAX_OUTPUT_TOKENS)
        request = AIRequest(
            request_key=facts.enquiry_id,
            enquiry_id=facts.enquiry_id,
            stage="reply",
            model=self._model,
            trusted_instructions=REPLY_SYSTEM_PROMPT,
            untrusted_text=_context(facts, locale),
            image_base64=None,
            output_schema_name="ReplySlots",
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )
        result = await call_structured(request, client=self._client, allow_live=True)
        cost = await self._allowance.settle(reservation, result.input_tokens, result.output_tokens)
        slots = ReplySlots.model_validate_json(result.output_json)
        validate_slots(slots)
        return slots, CallUsage(result.input_tokens, result.output_tokens, cost)


def live_available(settings: Any, *, now: datetime | None = None) -> tuple[bool, str | None]:
    """Whether a NEW run may start on the live provider, and if not, the honest reason."""
    if settings.ai_mode != "live":
        return False, "AI_MODE is fixture: no live model calls are configured."
    if not settings.openai_api_key or not settings.openai_text_model:
        return False, "No OpenAI key or text model is configured on the server."
    if settings.ai_confirmed_allowance_usd <= 0:
        return False, "The owner has not confirmed an AI allowance."
    expires = settings._parse_utc(settings.ai_allowance_expires_at)
    if expires is None or expires <= (now or datetime.now(timezone.utc)):
        return False, "The confirmed AI allowance has expired."
    return True, None


def require_live(settings: Any) -> None:
    ok, reason = live_available(settings)
    if not ok:
        raise PartsIQError("CREDIT_UNAVAILABLE", internal_detail=reason)
