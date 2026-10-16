"""F12 Conversation memory — persist typed state, resume by enquiry/revision, isolate threads."""
from __future__ import annotations

import unittest
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver

from app.controller import next_step
from app.events import ClaimedEvent, consume_event
from app.graph import build_graph
from app.handlers import WorkflowHandlers
from app.state import thread_id
from partsiq_common.contracts import EnquiryState, ItemInput, ItemState, WorkflowStep


def _item():
    return ItemState(
        id=uuid4(),
        request=ItemInput(description="filter", source_message_id=uuid4(), source_start=0, source_end=1),
        configuration_id=None, candidate_part_ids=[], selected_part_id=None, status="unresolved",
    )


def _state():
    return EnquiryState(
        enquiry_id=uuid4(), revision=1, session_generation=None, catalogue_version_id=None,
        items=[], step_count=0, pending_question=None, draft_id=None, verification_id=None, phase="",
    )


async def _passthrough(s):
    return s


def _handlers(intake):
    return WorkflowHandlers(
        intake=intake, identify=_passthrough, search=_passthrough, choose=_passthrough,
        plan=_passthrough, draft=_passthrough, verify=_passthrough,
    )


class ConversationMemory(unittest.IsolatedAsyncioTestCase):
    async def test_restart_retains_unresolved_question(self):
        async def intake(s):
            return s.model_copy(update={"items": [_item()], "pending_question": "fuel filter or separator?"})

        saver = InMemorySaver()
        graph = build_graph(_handlers(intake), saver)
        config = {"configurable": {"thread_id": thread_id(uuid4(), 1)}}
        await graph.ainvoke(_state(), config)

        # A fresh graph bound to the SAME saver/thread resumes the persisted state.
        resumed = build_graph(_handlers(intake), saver)
        snapshot = await resumed.aget_state(config)
        self.assertEqual(snapshot.values["pending_question"], "fuel filter or separator?")
        self.assertEqual(next_step(EnquiryState.model_validate(snapshot.values)), WorkflowStep.CLARIFY)

    async def test_foreign_thread_has_no_state(self):
        saver = InMemorySaver()
        graph = build_graph(_handlers(lambda s: s), saver)
        snapshot = await graph.aget_state({"configurable": {"thread_id": thread_id(uuid4(), 99)}})
        self.assertEqual(snapshot.values, {})

    async def test_old_revision_event_is_obsolete(self):
        class Store:
            async def claim(self, event_id):
                return ClaimedEvent(event_id, uuid4(), revision=1, session_generation=None)

            async def current(self, enquiry_id):
                return (2, None)  # enquiry has advanced to revision 2

            async def mark_obsolete(self, event_id):
                self.obsolete = True

            async def mark_processed(self, event_id):  # pragma: no cover
                raise AssertionError

            async def mark_retry(self, event_id):  # pragma: no cover
                raise AssertionError

            async def run(self, claim):  # pragma: no cover
                raise AssertionError

        outcome = await consume_event(uuid4(), store=Store())
        self.assertEqual(outcome.state, "obsolete")


if __name__ == "__main__":
    unittest.main(verbosity=2)
