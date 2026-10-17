"""The single wrapped path to OpenAI structured output (foundation 10).

Contract: ``call_structured(request: AIRequest) -> AIResult`` (an injected structured
``client`` is used in tests; a live client is built only when explicitly enabled).

Hard rules (prompt 10 steps 1-4, CONSTRAINTS rules 13, SECURITY.md trust boundaries):
  * The SDK is created with ``max_retries=0`` and a bounded timeout; a small bounded
    wrapper retry owns retries, so a failure is never retried by both layers.
  * The request's ``max_output_tokens`` is a HARD cap passed to the provider on every call.
  * The returned JSON is validated against the declared contract schema — invalid provider
    JSON RAISES (never a silent empty result); a failed dependency is never a success.
  * ``trusted_instructions`` become the system message; ``untrusted_text`` and any image
    travel in a SEPARATE user message, so customer/OCR data can never rewrite instructions.
  * No tool definitions are ever sent (prompt 10 step 3): the model has no write/approval
    surface.
  * ``openai`` is imported lazily, so this module imports with no key and no SDK present;
    a live call is BLOCKED unless the caller explicitly enables it, and only a safe error
    code + request id is logged — never the key, the untrusted text or the image bytes.
"""
from __future__ import annotations

import logging
from typing import Any

from partsiq.core.contracts import (
    AIRequest,
    AIResult,
    IntakeResult,
    NameplateResult,
    PartsProposal,
    ReplySlots,
    SummaryResult,
)
from partsiq.core.errors import PartsIQError

logger = logging.getLogger("partsiq.ai")

DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_ATTEMPTS = 2

# Output-schema name -> contract class used to validate the model's JSON. Only schemas
# in this table may be requested; an unknown schema is blocked, never guessed.
_SCHEMAS: dict[str, type] = {
    "IntakeResult": IntakeResult,
    "NameplateResult": NameplateResult,
    "PartsProposal": PartsProposal,
    "ReplySlots": ReplySlots,
    "SummaryResult": SummaryResult,
}


def build_openai_client(
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    api_key: str | None = None,
    allow_live: bool = False,
) -> Any:
    """Create an AsyncOpenAI client with retries disabled (the wrapper owns retries).

    A live client is BLOCKED by default: the provider is only reachable once an owner has
    confirmed a dedicated allowance and expiry (CONSTRAINTS rule 13), at which point the
    caller passes ``allow_live=True``. ``openai`` is imported lazily so this module (and
    its tests) import with no SDK and no key present.
    """
    if not allow_live:
        raise PartsIQError(
            "CREDIT_UNAVAILABLE",
            internal_detail="live OpenAI is blocked until a confirmed allowance is enabled",
        )
    from openai import AsyncOpenAI  # lazy: importing this module needs no key or SDK

    return AsyncOpenAI(max_retries=0, timeout=timeout, api_key=api_key)


def _schema_for(output_schema_name: str) -> type:
    schema = _SCHEMAS.get(output_schema_name)
    if schema is None:
        raise PartsIQError(
            "DEPENDENCY_UNAVAILABLE",
            internal_detail=f"unknown output schema {output_schema_name!r}",
        )
    return schema


def _build_messages(request: AIRequest) -> list[dict[str, Any]]:
    """System message = TRUSTED instructions; user message = UNTRUSTED data only.

    The split is the prompt-isolation boundary: customer/OCR text and image bytes are data
    carried in the user role and can never reinterpret the system instructions.
    """
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


def _validate_output(output_schema_name: str, output_json: str) -> None:
    """Raise if the model output does not match its declared contract schema.

    Invalid provider JSON is a failed attempt, never trusted output; the raise is what
    stops an empty/garbage response from progressing as if it were a success.
    """
    schema = _schema_for(output_schema_name)
    schema.model_validate_json(output_json)  # raises pydantic ValidationError on mismatch


async def call_structured(
    request: AIRequest,
    *,
    client: Any | None = None,
    allow_live: bool = False,
) -> AIResult:
    """Call OpenAI (up to ``MAX_ATTEMPTS``) and return validated structured output.

    ``client`` is an injected structured client in tests; when absent a live client is
    built only if ``allow_live`` is true (otherwise BLOCKED). The request's
    ``max_output_tokens`` is enforced as a hard provider cap on every attempt and the
    response is validated against the declared schema before it is returned.
    """
    # Validate the requested schema up front so a bad schema name never reaches the wire.
    _schema_for(request.output_schema_name)
    active_client = client if client is not None else build_openai_client(allow_live=allow_live)
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
                max_tokens=request.max_output_tokens,  # hard output-token cap
                response_format=response_format,
            )
            output_json = response.choices[0].message.content or ""
            _validate_output(request.output_schema_name, output_json)
            usage = response.usage
            return AIResult(
                output_json=output_json,
                input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
                output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
                provider_request_id=str(getattr(response, "id", "") or ""),
            )
        except PartsIQError:
            # A schema/dependency block is deterministic — retrying cannot help.
            raise
        except Exception as exc:  # noqa: BLE001 — classify to a safe code, never leak detail
            last_error = exc
            logger.warning(
                "ai call attempt failed",
                extra={
                    "stage": request.stage,
                    "attempt": attempt,
                    "request_key": str(request.request_key),
                    "error_type": type(exc).__name__,
                },
            )

    raise PartsIQError(
        "DEPENDENCY_UNAVAILABLE",
        internal_detail=(
            f"openai failed after {MAX_ATTEMPTS} attempts: "
            f"{type(last_error).__name__ if last_error else 'unknown'}"
        ),
    )
