"""Agent-collaboration mode: addressed specialist exchanges under a code-owned controller.

The four SPECIALISTS (intake, nameplate, parts, reply) propose actions — a message to another
participant, a tool call, a clarification for the customer, a delegation that needs consent, or
"ready for human review". They never act directly. The :class:`Controller`:

* routes only along the declared matrix (``ROUTES``) and accepts only declared kinds;
* lets each specialist call only its allow-listed deterministic SERVICES (``TOOLS``), whose
  arguments are item ids — a tool always reads the confirmed record, so a model cannot pass its
  own query, configuration, quantity or stock figure;
* rejects proposals whose parts are not in the code-computed compatible set, and refuses
  "ready for review" unless the deterministic verification passed for the current revision;
* bounds message size, actions per turn, agent turns, tool calls, tokens, cost and wall time;
* drops repeated identical exchanges and blocks a run that keeps looping;
* persists every accepted or rejected action as an ordered exchange (observable requests,
  outputs and tool outcomes — never hidden reasoning).

There is no broadcast and no write tool. Approval and publication remain the existing human
review flow; nothing here can approve, publish, alter stock or the catalogue.

Fixture specialists below are deterministic policies over real tool results. Live specialists
(``live_specialists.py``) propose the same structured actions through the wrapped OpenAI client.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Protocol

AGENTS: tuple[str, ...] = ("intake", "nameplate", "parts", "reply")
SERVICES: tuple[str, ...] = ("identification", "compatibility_search", "fulfilment", "verification")

# Human-facing names for the activity view.
PARTICIPANT_LABELS: dict[str, str] = {
    "intake": "Intake specialist",
    "nameplate": "Nameplate specialist",
    "parts": "Parts specialist",
    "reply": "Reply specialist",
    "identification": "Identification service",
    "compatibility_search": "Compatibility search",
    "fulfilment": "Fulfilment service",
    "verification": "Verification service",
    "controller": "Run controller",
    "customer": "Customer",
    "reviewer": "Reviewer",
    "workflow": "Guided workflow",
}

KIND_LABELS: dict[str, str] = {
    "task": "Task assigned",
    "request_info": "Information requested",
    "evidence": "Evidence returned",
    "proposal": "Candidate proposal",
    "challenge": "Proposal challenged",
    "handoff": "Handoff",
    "finding": "Finding",
    "clarification_request": "Clarification required",
    "delegation_request": "Delegation awaiting consent",
    "consent_result": "Delegation decision",
    "tool_call": "Tool call",
    "tool_result": "Tool result",
    "user_instruction": "User instruction accepted",
    "user_answer": "Customer answer",
    "control": "Run control",
    "limit_reached": "Limit reached",
    "action_rejected": "Action rejected by policy",
    "late_result_discarded": "Late result discarded",
    "ready_for_review": "Ready for human review",
    "step_completed": "Workflow step",
    "provider_unavailable": "Provider unavailable",
}

# sender -> {kind -> allowed recipients}. Anything not listed is rejected by the controller.
ROUTES: dict[str, dict[str, frozenset[str]]] = {
    "intake": {
        "request_info": frozenset({"nameplate", "parts"}),
        "handoff": frozenset({"parts"}),
        "clarification_request": frozenset({"customer"}),
        "tool_call": frozenset({"identification"}),
        "finding": frozenset({"controller", "reply"}),
    },
    "nameplate": {
        "evidence": frozenset({"intake"}),
        "finding": frozenset({"intake"}),
    },
    "parts": {
        "proposal": frozenset({"reply"}),
        "evidence": frozenset({"reply"}),
        "request_info": frozenset({"intake"}),
        "challenge": frozenset({"intake"}),
        "clarification_request": frozenset({"customer"}),
        "delegation_request": frozenset({"compatibility_search"}),
        "tool_call": frozenset({"identification", "compatibility_search", "fulfilment"}),
        "finding": frozenset({"controller"}),
    },
    "reply": {
        "request_info": frozenset({"parts"}),
        "challenge": frozenset({"parts"}),
        "tool_call": frozenset({"verification"}),
        "ready_for_review": frozenset({"controller"}),
        "finding": frozenset({"controller"}),
    },
}

# Specialist -> tools it may call (deterministic services only; none of them writes stock,
# catalogue, approval or publication state).
TOOLS: dict[str, frozenset[str]] = {
    "intake": frozenset({"identification"}),
    "nameplate": frozenset(),
    "parts": frozenset({"identification", "compatibility_search", "fulfilment"}),
    "reply": frozenset({"verification"}),
}

# Tool -> accepted argument names (all ids into the confirmed record).
TOOL_ARGS: dict[str, frozenset[str]] = {
    "identification": frozenset({"item_id"}),
    "compatibility_search": frozenset({"item_id", "mode"}),
    "fulfilment": frozenset({"item_id"}),
    "verification": frozenset(),
}
TOOL_MODES = frozenset({"standard", "alternatives", "in_stock_alternatives"})

# Delegations that need the customer's (or overseer's) consent before the controller runs them.
CONSENT_REQUIRED: frozenset[str] = frozenset({"search_alternatives"})

MAX_ACTIONS_PER_TURN = 3
MAX_SUMMARY_CHARS = 600
MAX_CONSECUTIVE_REJECTIONS = 2


@dataclass
class Action:
    """One proposed action from a specialist turn (validated before anything executes)."""

    kind: str
    recipient: str
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    tool: str | None = None
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class Turn:
    actions: list[Action]
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_usd: Any = 0


class PolicyViolation(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def signature(sender: str, action: Action) -> str:
    body = json.dumps(
        {"s": sender, "r": action.recipient, "k": action.kind, "t": action.tool, "a": action.args, "m": action.summary, "d": action.data},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def validate_action(sender: str, action: Action, *, max_bytes: int, item_ids: set[str]) -> None:
    """Raise :class:`PolicyViolation` unless ``action`` is permitted for ``sender``."""
    routes = ROUTES.get(sender)
    if routes is None:
        raise PolicyViolation("UNKNOWN_SENDER", f"{sender} may not send messages")
    allowed = routes.get(action.kind)
    if allowed is None:
        raise PolicyViolation("KIND_NOT_ALLOWED", f"{sender} may not send '{action.kind}'")
    if action.recipient not in allowed:
        raise PolicyViolation("RECIPIENT_NOT_ALLOWED", f"{sender} may not send '{action.kind}' to {action.recipient}")
    if not isinstance(action.summary, str) or not action.summary.strip():
        raise PolicyViolation("EMPTY_SUMMARY", "every exchange needs a concise summary")
    if len(action.summary) > MAX_SUMMARY_CHARS:
        raise PolicyViolation("SUMMARY_TOO_LONG", "summary exceeds the size limit")
    size = len(json.dumps(action.data, default=str).encode("utf-8"))
    if size > max_bytes:
        raise PolicyViolation("PAYLOAD_TOO_LARGE", f"payload of {size} bytes exceeds {max_bytes}")
    if action.kind == "tool_call":
        tool = action.tool or action.recipient
        if tool != action.recipient:
            raise PolicyViolation("TOOL_MISMATCH", "tool name must match the addressed service")
        if tool not in TOOLS.get(sender, frozenset()):
            raise PolicyViolation("TOOL_NOT_ALLOWED", f"{sender} may not call {tool}")
        extra = set(action.args) - TOOL_ARGS[tool]
        if extra:
            raise PolicyViolation("UNKNOWN_ARGUMENT", f"unsupported tool arguments: {sorted(extra)}")
        if "item_id" in TOOL_ARGS[tool]:
            if str(action.args.get("item_id")) not in item_ids:
                raise PolicyViolation("UNKNOWN_ITEM", "tool call must reference an item of this enquiry")
        mode = action.args.get("mode", "standard")
        if tool == "compatibility_search" and mode not in TOOL_MODES:
            raise PolicyViolation("UNKNOWN_MODE", "unsupported search mode")
    if action.kind == "delegation_request":
        if action.data.get("action") not in CONSENT_REQUIRED:
            raise PolicyViolation("UNKNOWN_DELEGATION", "unsupported delegation")
        if str(action.data.get("item_id")) not in item_ids:
            raise PolicyViolation("UNKNOWN_ITEM", "delegation must reference an item of this enquiry")


class Board(Protocol):
    """Read-only view a specialist receives (controller-owned, code-computed facts)."""

    def snapshot(self) -> dict[str, Any]: ...


class Specialist(Protocol):
    name: str
    source: str

    async def respond(self, message: dict[str, Any], board: dict[str, Any]) -> Turn: ...


# ---------------------------------------------------------------------------------------------
# Fixture specialists: deterministic policies over the controller's real tool results.
# ---------------------------------------------------------------------------------------------


def _items(board: dict[str, Any]) -> list[dict[str, Any]]:
    return list(board.get("items", []))


def _item(board: dict[str, Any], item_id: str) -> dict[str, Any] | None:
    return next((i for i in _items(board) if i["item_id"] == item_id), None)


class FixtureIntake:
    name = "intake"
    source = "fixture"

    async def respond(self, message: dict[str, Any], board: dict[str, Any]) -> Turn:
        kind = message["kind"]
        items = _items(board)
        if kind == "task":
            if board.get("attachment_pending"):
                return Turn([Action("request_info", "nameplate", "Please read the model and serial from the attached nameplate photo.", {"attachment": True})])
            missing_model = next((i for i in items if not i.get("model_text")), None)
            if missing_model is not None:
                return Turn([Action("clarification_request", "customer", "The machine model is missing; asking the customer for it.", {"code": "needs_model", "item_id": missing_model["item_id"]})])
            unidentified = [i for i in items if i.get("configuration_id") is None]
            if unidentified:
                first = unidentified[0]
                reason = "no serial was given" if not first.get("serial_text") else "confirming the configuration"
                return Turn([Action("tool_call", "identification", f"Model {first['model_text']} given but {reason}; requesting identification.", {}, tool="identification", args={"item_id": first["item_id"]})])
            return Turn([_handoff(items)])
        if kind == "tool_result" and message["sender"] == "identification":
            data = message["data"]
            if data.get("state") != "resolved":
                return Turn([Action("clarification_request", "customer", f"Identification needs more information ({data.get('code')}); asking the customer.", {"code": data.get("code"), "item_id": data.get("item_id")})])
            pending = [i for i in items if i.get("configuration_id") is None]
            if pending:
                return Turn([Action("tool_call", "identification", f"Identifying the machine for {pending[0]['description']}.", {}, tool="identification", args={"item_id": pending[0]["item_id"]})])
            return Turn([_handoff(items)])
        if kind == "evidence" and message["sender"] == "nameplate":
            return Turn([Action("clarification_request", "customer", "Nameplate identifiers must be confirmed by the customer before use.", {"code": "confirm_identifiers"})])
        if kind == "request_info" and message["sender"] == "parts":
            return Turn([Action("clarification_request", "customer", message["summary"], {"code": message["data"].get("code", "needs_serial"), "item_id": message["data"].get("item_id")})])
        if kind == "user_instruction":
            if message["data"].get("factual_change"):
                return Turn([Action("finding", "controller", "The instruction changes machine facts; it must be sent as a new customer message so a new revision is verified.", {"factual_change": True})])
            return Turn([Action("finding", "reply", "Customer instruction noted for the reply (cannot change facts or approval).", {"instruction": message["data"].get("text", "")[:300]})])
        return Turn([])


def _handoff(items: list[dict[str, Any]]) -> Action:
    lines = []
    for i in items:
        qty = i.get("quantity") or "?"
        lines.append(f"{qty} × {i['description']} for {i.get('configuration_label') or i.get('model_text') or 'unknown machine'}")
    return Action("handoff", "parts", "Request understood: " + "; ".join(lines) + ". Please find compatible parts.", {"items": [i["item_id"] for i in items]})


class FixtureNameplate:
    name = "nameplate"
    source = "fixture"

    async def respond(self, message: dict[str, Any], board: dict[str, Any]) -> Turn:
        plate = board.get("nameplate") or {}
        if message["kind"] == "request_info":
            if plate.get("issues"):
                return Turn([Action("finding", "intake", f"The photo could not be read reliably ({', '.join(plate['issues'])}).", {"issues": plate["issues"]})])
            return Turn([Action("evidence", "intake", f"Nameplate shows model {plate.get('model_text')} and serial {plate.get('serial_text')} (fixture vision; needs customer confirmation).", {"model_text": plate.get("model_text"), "serial_text": plate.get("serial_text"), "confirmation_required": True})])
        return Turn([])


class FixtureParts:
    name = "parts"
    source = "fixture"

    async def respond(self, message: dict[str, Any], board: dict[str, Any]) -> Turn:
        kind, sender, data = message["kind"], message["sender"], message.get("data", {})
        items = _items(board)
        if kind == "handoff":
            return self._next(items)
        if kind == "tool_result" and sender == "identification":
            if data.get("state") != "resolved":
                return Turn([Action("request_info", "intake", "The configuration is still unknown; the customer must supply the serial number.", {"code": data.get("code", "needs_serial"), "item_id": data.get("item_id")})])
            return self._next(items)
        if kind == "tool_result" and sender == "compatibility_search":
            item_id = data["item_id"]
            mode = data.get("mode", "standard")
            if mode == "in_stock_alternatives":
                alts = data.get("alternatives", [])
                summary = (
                    "No other compatible part is in stock at the destination; the shortage stands."
                    if not alts
                    else "Compatible alternatives with stock exist (listed for the reviewer); keeping the customer's requested part."
                )
                return Turn([Action("evidence", "reply", summary, {"item_id": item_id, "alternatives": alts[:3]})])
            action = data.get("action")
            if action == "resolve":
                return Turn([Action("tool_call", "fulfilment", f"Compatible part {data.get('selected_part_number')} found; planning stock.", {}, tool="fulfilment", args={"item_id": item_id})])
            if action == "mismatch":
                return Turn([Action(
                    "delegation_request", "compatibility_search",
                    f"The quoted number {', '.join(data.get('incompatible_numbers', []))} does not fit this machine. May I search compatible alternatives of the same part type instead?",
                    {"action": "search_alternatives", "item_id": item_id},
                )])
            if action == "clarify":
                names = [c["part_number"] + " " + c["name_en"] for c in data.get("candidates", [])[:3]]
                return Turn([Action("clarification_request", "customer", "Several compatible parts match closely: " + "; ".join(names) + ". Asking the customer which one.", {"code": "ambiguous_part", "item_id": item_id})])
            return Turn([Action("finding", "controller", "No compatible part exists in the active catalogue for this item; staff must handle it.", {"item_id": item_id, "needs_staff": True})])
        if kind == "tool_result" and sender == "fulfilment":
            if data.get("state") == "needs_information":
                return Turn([Action("clarification_request", "customer", "A compatible part is selected but the quantity is missing; asking the customer.", {"code": "quantity", "item_id": data.get("item_id")})])
            return self._next(items)
        if kind == "consent_result":
            if data.get("approved"):
                return Turn([Action("tool_call", "compatibility_search", "Consent given; searching compatible alternatives of the same part type.", {}, tool="compatibility_search", args={"item_id": data["item_id"], "mode": "alternatives"})])
            return Turn([Action("clarification_request", "customer", "Alternative search declined; asking the customer to re-check the part number or nameplate.", {"code": "mismatch", "item_id": data["item_id"]})])
        if kind in ("request_info", "challenge") and sender == "reply":
            if data.get("need") == "in_stock_alternatives":
                return Turn([Action("tool_call", "compatibility_search", "Checking whether another compatible part is in stock at the destination.", {}, tool="compatibility_search", args={"item_id": data["item_id"], "mode": "in_stock_alternatives"})])
            if data.get("need") == "replan":
                return Turn([Action("tool_call", "fulfilment", "Verification flagged the plan; re-planning with fresh stock.", {}, tool="fulfilment", args={"item_id": data["item_id"]})])
            return Turn([self._proposal(items)])
        return Turn([])

    def _next(self, items: list[dict[str, Any]]) -> Turn:
        for i in items:
            if i.get("status") == "needs_information":
                return Turn([])
            if i.get("configuration_id") is None:
                return Turn([Action("tool_call", "identification", f"Identifying the machine for {i['description']}.", {}, tool="identification", args={"item_id": i["item_id"]})])
            if not i.get("searched"):
                return Turn([Action("tool_call", "compatibility_search", f"Searching compatible parts for {i['description']} on {i.get('configuration_label')}.", {}, tool="compatibility_search", args={"item_id": i["item_id"]})])
            if i.get("status") == "ready" and not i.get("planned"):
                return Turn([Action("tool_call", "fulfilment", f"Planning stock for {i.get('selected_part_number')}.", {}, tool="fulfilment", args={"item_id": i["item_id"]})])
        if any(i.get("status") == "ready" for i in items) and all(i.get("status") in ("ready", "unavailable") for i in items):
            return Turn([self._proposal(items)])
        return Turn([])

    @staticmethod
    def _proposal(items: list[dict[str, Any]]) -> Action:
        ready = [i for i in items if i.get("status") == "ready"]
        lines = [
            f"{i.get('selected_part_number')} × {i.get('quantity')} ({i.get('plan_message') or 'planned'})"
            for i in ready
        ]
        return Action(
            "proposal", "reply", "Proposed selection: " + "; ".join(lines),
            {
                "items": [
                    {
                        "item_id": i["item_id"],
                        "part_id": i.get("selected_part_id"),
                        "part_number": i.get("selected_part_number"),
                        "source_reference": i.get("source_reference"),
                        "shortage": i.get("shortage", 0),
                    }
                    for i in ready
                ]
            },
        )


class FixtureReply:
    name = "reply"
    source = "fixture"

    async def respond(self, message: dict[str, Any], board: dict[str, Any]) -> Turn:
        kind, sender, data = message["kind"], message["sender"], message.get("data", {})
        if kind == "proposal":
            missing = [p for p in data.get("items", []) if not p.get("source_reference")]
            if missing:
                return Turn([Action("challenge", "parts", "The proposal lacks a fitment source reference; I cannot draft an evidence-backed explanation.", {"need": "evidence", "item_id": missing[0]["item_id"]})])
            short = [p for p in data.get("items", []) if int(p.get("shortage") or 0) > 0]
            checked = set(board.get("alternatives_checked", []))
            unchecked = [p for p in short if p["item_id"] not in checked]
            if unchecked:
                return Turn([Action("request_info", "parts", "The plan has a shortage. Before drafting a partial-availability reply, check whether another compatible part is in stock.", {"need": "in_stock_alternatives", "item_id": unchecked[0]["item_id"]})])
            return Turn([Action("tool_call", "verification", "Rendering the reply from verified facts and running the verification gate.", {}, tool="verification")])
        if kind == "evidence" and sender == "parts":
            return Turn([Action("tool_call", "verification", "Alternatives checked; rendering the reply and running the verification gate.", {}, tool="verification")])
        if kind == "tool_result" and sender == "verification":
            if data.get("passed"):
                return Turn([Action("ready_for_review", "controller", "Draft rendered from verified facts; all verification rules passed. Ready for human review.", {"draft_id": data.get("draft_id")})])
            failures = data.get("failures", [])
            if "STALE_STOCK" in failures or "OVERALLOCATION" in failures:
                if not board.get("replanned"):
                    item_id = (board.get("items") or [{}])[0].get("item_id")
                    return Turn([Action("challenge", "parts", f"Verification failed ({', '.join(failures)}); please re-plan with fresh stock.", {"need": "replan", "item_id": item_id})])
            return Turn([Action("finding", "controller", f"Verification failed ({', '.join(failures)}); staff must review.", {"failures": failures, "needs_staff": True})])
        if kind == "finding" and sender == "intake":
            return Turn([])
        return Turn([])


def fixture_specialists() -> dict[str, Specialist]:
    return {
        "intake": FixtureIntake(),
        "nameplate": FixtureNameplate(),
        "parts": FixtureParts(),
        "reply": FixtureReply(),
    }
