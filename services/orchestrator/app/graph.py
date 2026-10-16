"""LangGraph assembly.

Contract: ``def build_graph(handlers, checkpointer) -> CompiledStateGraph``.

The graph is driven entirely by the deterministic controller: a conditional router calls
``next_step`` and dispatches to the matching executable node, or ends (pausing durably at
the checkpoint) when the next step is a blocking interrupt or a terminal state. Each
executable node runs its registered handler and increments the bounded step counter.
"""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from app.controller import next_step
from app.handlers import WorkflowHandlers
from partsiq_common.contracts import EnquiryState, WorkflowStep

# Executable steps -> node name. Blocking/terminal steps are NOT nodes; they end the run.
EXECUTABLE: dict[WorkflowStep, str] = {
    WorkflowStep.INTAKE: "intake",
    WorkflowStep.IDENTIFY: "identify",
    WorkflowStep.SEARCH: "search",
    WorkflowStep.CHOOSE: "choose",
    WorkflowStep.PLAN: "plan",
    WorkflowStep.DRAFT: "draft",
    WorkflowStep.VERIFY: "verify",
}


def _route(state: EnquiryState) -> str:
    return EXECUTABLE.get(next_step(state), END)


def _make_node(handler):
    async def node(state: EnquiryState) -> EnquiryState:
        updated = await handler(state)
        return updated.model_copy(update={"step_count": updated.step_count + 1})

    return node


def build_graph(handlers: WorkflowHandlers, checkpointer: Any):
    """Compile the workflow graph against a checkpointer (Postgres in prod, memory in tests)."""
    builder = StateGraph(EnquiryState)
    node_handlers = {
        "intake": handlers.intake, "identify": handlers.identify, "search": handlers.search,
        "choose": handlers.choose, "plan": handlers.plan, "draft": handlers.draft, "verify": handlers.verify,
    }
    for name, handler in node_handlers.items():
        builder.add_node(name, _make_node(handler))

    route_map = {name: name for name in node_handlers}
    route_map[END] = END
    builder.set_conditional_entry_point(_route, route_map)
    for name in node_handlers:
        builder.add_conditional_edges(name, _route, route_map)
    return builder.compile(checkpointer=checkpointer)
