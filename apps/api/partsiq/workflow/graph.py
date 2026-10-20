"""LangGraph assembly for the single-package workflow (authoritative engine).

Contract: ``build_graph(handlers, checkpointer) -> CompiledStateGraph``.

The graph is driven ENTIRELY by the deterministic controller: a conditional router calls
:func:`partsiq.workflow.transitions.next_step` and dispatches to the matching executable node,
or ends — pausing durably at the checkpoint — when the next step is a blocking interrupt
(await_ocr / confirm / clarify / review) or a terminal state (complete / needs_staff). There is
NO LLM supervisor: `next_step` is pure Python over the typed :class:`EnquiryState`, so routing is
testable on labelled cases and cannot be steered by model output (CONSTRAINTS rule 5).

This replaces the earlier plain-Python loop as the authoritative engine. The deterministic
transition table (`transitions.py`) is reused verbatim as the router; the per-step business
functions (intake extraction, identification, compatibility search, fulfilment, reply, the
verification gate) are reused via injected handlers (see ``handlers.py``). Durable state lives in
the LangGraph checkpointer keyed by ``thread_id(enquiry_id, revision)`` (Postgres in prod,
InMemorySaver in fixture/tests); the business records (enquiries/revisions/jobs/audit + the
step-outcome timeline) remain authoritative in PostgreSQL. See
``docs/adr/0001-langgraph-workflow-engine.md`` for the ownership contract.
"""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from ..core.contracts import EnquiryState, WorkflowStep
from .handlers import GraphHandlers
from .transitions import next_step

# Executable steps -> node name. Blocking/terminal steps are NOT nodes; they end the run and the
# checkpointer persists the paused state for out-of-band resume (OCR job, customer answer, review).
EXECUTABLE: dict[WorkflowStep, str] = {
    WorkflowStep.INTAKE: "intake",
    WorkflowStep.IDENTIFY: "identify",
    WorkflowStep.SEARCH: "search",
    WorkflowStep.CHOOSE: "choose",
    WorkflowStep.PLAN: "plan",
    WorkflowStep.DRAFT: "draft",
    WorkflowStep.VERIFY: "verify",
}


def route_step(state: EnquiryState) -> str:
    """Deterministic router: the next executable node, or END to pause/stop. Never an LLM."""
    return EXECUTABLE.get(next_step(state), END)


# The typed contract models stored inside the checkpointed EnquiryState. Registering them with
# the serializer keeps the checkpoint forward-compatible (langgraph will otherwise block
# unregistered msgpack types in a future release) and avoids pickle fallback.
_CHECKPOINT_TYPES = [
    ("partsiq.core.contracts", "EnquiryState"),
    ("partsiq.core.contracts", "ItemState"),
    ("partsiq.core.contracts", "ItemInput"),
]


def memory_checkpointer():
    """An InMemorySaver whose serializer explicitly allows the PartsIQ contract types.

    Used in fixture/test mode. DB mode builds the Postgres checkpointer from the workflow pool at
    startup with the same allowed-types serde.
    """
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    return InMemorySaver(serde=JsonPlusSerializer(allowed_msgpack_modules=_CHECKPOINT_TYPES))


def _make_node(handler):
    async def node(state: EnquiryState) -> EnquiryState:
        updated = await handler(state)
        return updated.model_copy(update={"step_count": updated.step_count + 1})

    return node


def build_graph(handlers: GraphHandlers, checkpointer: Any, *, interrupt_before: list[str] | None = None):
    """Compile the workflow graph against a checkpointer (Postgres in prod, memory in tests).

    Every required node handler must be present; the readiness gate refuses to run a graph with a
    missing node rather than shipping a fake-success node (prompt 09).
    """
    missing = handlers.missing()
    if missing:
        raise ValueError(f"cannot build workflow graph; missing node handlers: {missing}")

    builder = StateGraph(EnquiryState)
    node_handlers = {
        "intake": handlers.intake,
        "identify": handlers.identify,
        "search": handlers.search,
        "choose": handlers.choose,
        "plan": handlers.plan,
        "draft": handlers.draft,
        "verify": handlers.verify,
    }
    for name, handler in node_handlers.items():
        builder.add_node(name, _make_node(handler))

    route_map: dict[str, str] = {name: name for name in node_handlers}
    route_map[END] = END
    builder.set_conditional_entry_point(route_step, route_map)
    for name in node_handlers:
        builder.add_conditional_edges(name, route_step, route_map)
    # ``interrupt_before`` (optional) pauses before the named nodes so a caller can drive the
    # graph one node per call and apply pause/cancel at a safe boundary (workspace runner).
    if interrupt_before:
        return builder.compile(checkpointer=checkpointer, interrupt_before=interrupt_before)
    return builder.compile(checkpointer=checkpointer)
