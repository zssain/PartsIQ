"""The single wrapped path to OpenAI structured output.

Contract: ``call_structured(request: AIRequest, budget: BudgetReservation) -> AIResult``.

Hard rules (prompt 01, CONSTRAINTS.md rules 5-6, F64/F67):
  * Explicit timeout and output-token cap on every call.
  * The SDK is created with ``max_retries=0`` and the wrapper makes at most 2 attempts,
    so a failure is never retried by both layers.
  * Only a safe error code + request id is logged — never the key, the untrusted text
    or the image bytes.
  * ``trusted_instructions`` become the system message; ``untrusted_text`` is a separate
    user message, so customer text cannot silently rewrite the instructions.
  * The returned JSON is validated against the named contract schema, so a malformed
    model response is treated as a failed attempt rather than trusted output.
"""
from __future__ import annotations

import logging
from typing import Any

from partsiq_common.contracts import (
    AIRequest,
    AIResult,
    BudgetReservation,
    IntakeResult,
    NameplateResult,
    PartsProposal,
    ReplySlots,
    SummaryResult,
)
from partsiq_common.errors import PartsIQError
from partsiq_common.telemetry import Tracer

logger = logging.getLogger("partsiq.ai")

DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_ATTEMPTS = 2

# Output-schema name -> contract class used to validate the model's JSON.
_SCHEMAS: dict[str, type] = {
    "IntakeResult": IntakeResult,
    "NameplateResult": NameplateResult,
    "PartsProposal": PartsProposal,
    "ReplySlots": ReplySlots,
    "SummaryResult": SummaryResult,
}


def build_openai_client(timeout: float = DEFAULT_TIMEOUT_SECONDS, api_key: str | None = None) -> Any:
    """Create an AsyncOpenAI client with retries disabled (the wrapper owns retries)."""
    from openai import AsyncOpenAI  # imported lazily so importing this module needs no key

    return AsyncOpenAI(max_retries=0, timeout=timeout, api_key=api_key)


def _build_messages(request: AIRequest) -> list[dict[str, Any]]:
    """System message = trusted instructions; user message = untrusted content only."""
    user_content: list[dict[str, Any]] = [{"type": "text", "text": request.untrusted_text}]
    if request.image_base64 is not None:
        user_content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{request.image_base64}"},
            }
        )
    return [
        {"role": "system", "content": request.trusted_instructions},
        {"role": "user", "content": user_content},
    ]


def _validate_output(schema_name: str, output_json: str) -> None:
    """Raise if the model output does not match its declared contract schema."""
    model = _SCHEMAS.get(schema_name)
    if model is None:
        raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail=f"unknown schema {schema_name!r}")
    model.model_validate_json(output_json)  # raises pydantic ValidationError on mismatch


async def call_structured(
    request: AIRequest,
    budget: BudgetReservation,
    *,
    client: Any | None = None,
    tracer: Tracer | None = None,
) -> AIResult:
    """Call OpenAI once (up to MAX_ATTEMPTS) and return validated structured output.

    ``budget`` is a reservation already taken by the caller against the allowance
    ledger; it is threaded through for correlation and cost settlement. An optional
    ``tracer`` emits a redacted span per outcome (prompt 23, F67) — propagating the
    request/enquiry ids and the stage/status/token counts — and never raises, so a
    tracing outage cannot affect the call or the local budget accounting.
    """
    active_client = client or build_openai_client()
    messages = _build_messages(request)
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": request.output_schema_name,
            "schema": _SCHEMAS[request.output_schema_name].model_json_schema(),
            "strict": True,
        },
    }

    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = await active_client.chat.completions.create(
                model=request.model,
                messages=messages,
                max_tokens=request.max_output_tokens,
                response_format=response_format,
            )
            output_json = response.choices[0].message.content or ""
            _validate_output(request.output_schema_name, output_json)
            usage = response.usage
            result = AIResult(
                output_json=output_json,
                input_tokens=getattr(usage, "prompt_tokens", 0),
                output_tokens=getattr(usage, "completion_tokens", 0),
                provider_request_id=getattr(response, "id", "") or "",
            )
            if tracer is not None:  # redacted span; never raises (F67)
                tracer.emit(
                    "ai.call",
                    {"stage": request.stage, "model": request.model, "attempt": attempt, "status": "ok",
                     "input_tokens": result.input_tokens, "output_tokens": result.output_tokens},
                    request_id=str(request.request_key),
                    enquiry_id=str(request.enquiry_id) if request.enquiry_id else None,
                )
            return result
        except Exception as exc:  # noqa: BLE001 — classify to a safe code, never leak detail
            last_error = exc
            logger.warning(
                "ai call attempt failed",
                extra={
                    "stage": request.stage,
                    "attempt": attempt,
                    "reservation_id": str(budget.id),
                    "request_key": str(request.request_key),
                    "error_type": type(exc).__name__,
                },
            )

    if tracer is not None:
        tracer.emit(
            "ai.call",
            {"stage": request.stage, "model": request.model, "attempt": MAX_ATTEMPTS, "status": "error",
             "error_type": type(last_error).__name__ if last_error else "unknown"},
            request_id=str(request.request_key),
            enquiry_id=str(request.enquiry_id) if request.enquiry_id else None,
        )
    raise PartsIQError(
        "DEPENDENCY_UNAVAILABLE",
        internal_detail=f"openai failed after {MAX_ATTEMPTS} attempts: {type(last_error).__name__}",
    )
