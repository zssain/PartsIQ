"""F48 Input isolation (owner: orchestrator; depends on 10-13, 16).

The hard boundary against prompt injection: customer text, OCR and imported evidence are DATA,
never instructions. A model may only ask to call a tool from a small READ-ONLY allowlist, with
strictly typed and size-bounded arguments, within the step budget. validate_tool_call is the
single gate every model-proposed tool call passes before dispatch — so an injected instruction
cannot invoke a write tool, change roles, reveal a secret, or smuggle an extra argument. The
tool's string arguments (a search query, a serial) stay inert data: a rogue instruction inside a
query is just a query. Tool RESULTS are likewise returned as data (label_tool_result), never fed
back as trusted instructions, and model-produced templates are never executed.
"""
from __future__ import annotations

import json

from partsiq_common.contracts import Contract, ToolContext

MAX_ARGS_BYTES = 4096

# The ONLY tools a model may call — both read-only specialist tools (prompt 11). There is
# deliberately no write/approve/assign/publish/role/secret tool here, so none can be invoked.
_TOOL_ARG_TYPES: dict[str, dict[str, type]] = {
    "identify": {"query": str, "serial": str},
    "search_parts": {"configuration_id": int, "query": str, "limit": int},
}
_REQUIRED_ARGS: dict[str, set[str]] = {
    "identify": {"query"},
    "search_parts": {"configuration_id", "query"},
}
_NULLABLE_ARGS: dict[str, set[str]] = {
    "identify": {"serial"},
    "search_parts": {"limit"},
}


class F48Request(Contract):
    tool_name: str
    arguments_json: str
    context: ToolContext


class F48Result(Contract):
    allowed: bool
    reason_code: str | None


def _deny(code: str) -> F48Result:
    return F48Result(allowed=False, reason_code=code)


def validate_tool_call(request: F48Request) -> F48Result:
    """Allow only an allowlisted read tool with typed, bounded arguments inside the step budget."""
    spec = _TOOL_ARG_TYPES.get(request.tool_name)
    if spec is None:
        return _deny("UNKNOWN_TOOL")  # write/role/secret tools are not on the allowlist at all
    if request.context.max_calls <= 0:
        return _deny("STEP_BUDGET_EXHAUSTED")
    if len(request.arguments_json.encode("utf-8")) > MAX_ARGS_BYTES:
        return _deny("ARGUMENTS_TOO_LARGE")
    try:
        arguments = json.loads(request.arguments_json)
    except (ValueError, TypeError):
        return _deny("MALFORMED_ARGUMENTS")
    if not isinstance(arguments, dict):
        return _deny("MALFORMED_ARGUMENTS")
    if set(arguments) - set(spec):
        return _deny("MALFORMED_ARGUMENTS")  # an unknown key (e.g. "role") is rejected
    if _REQUIRED_ARGS[request.tool_name] - set(arguments):
        return _deny("MALFORMED_ARGUMENTS")
    for key, value in arguments.items():
        if value is None:
            if key in _NULLABLE_ARGS[request.tool_name]:
                continue
            return _deny("MALFORMED_ARGUMENTS")
        expected = spec[key]
        # bool is a subtype of int — reject it explicitly so flags cannot pose as numbers.
        if expected is int and isinstance(value, bool):
            return _deny("MALFORMED_ARGUMENTS")
        if not isinstance(value, expected):
            return _deny("MALFORMED_ARGUMENTS")
    return F48Result(allowed=True, reason_code=None)


def label_tool_result(result_text: str) -> str:
    """Return a tool result marked as DATA so it is never re-interpreted as an instruction.

    Rogue instructions inside a tool result stay inert: the caller places this labelled text in
    the untrusted-data channel, never in trusted instructions.
    """
    return f"[tool-result-data]\n{result_text}"
