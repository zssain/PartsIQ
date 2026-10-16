"""Acceptance tests for prompt 09 — deterministic durable workflow (foundation gate).

Offline: the controller is pure; the graph compiles against an in-memory checkpointer
with injected test-double handlers (no fake-success shipped in app code); event
consumption runs against a fake store. The Postgres checkpointer + live DB inbox are
integration-only and reported BLOCKED.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "partsiq_common"))
sys.path.insert(0, str(REPO_ROOT / "services" / "orchestrator"))

from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

from app.controller import MAX_STEPS, next_step  # noqa: E402
from app.events import ClaimedEvent, consume_event  # noqa: E402
from app.graph import build_graph  # noqa: E402
from app.handlers import WorkflowHandlers, is_ready, missing_handlers  # noqa: E402
from app.state import thread_id  # noqa: E402
from partsiq_common.contracts import EnquiryState, ItemInput, ItemState, WorkflowStep  # noqa: E402


def item(status="unresolved", config=None, candidates=(), selected=None):
    return ItemState(
        id=uuid4(),
        request=ItemInput(description="oil filter", source_message_id=uuid4(), source_start=0, source_end=3),
        configuration_id=config, candidate_part_ids=list(candidates), selected_part_id=selected, status=status,
    )


def state(items=None, *, step=0, phase="", pending=None, draft=None, verification=None):
    return EnquiryState(
        enquiry_id=uuid4(), revision=1, session_generation=None, catalogue_version_id=None,
        items=items if items is not None else [], step_count=step, pending_question=pending,
        draft_id=draft, verification_id=verification, phase=phase,
    )


class ControllerTransitions(unittest.TestCase):
    def test_empty_items_intake(self):
        self.assertEqual(next_step(state([])), WorkflowStep.INTAKE)

    def test_await_ocr_and_confirm_phases(self):
        self.assertEqual(next_step(state([item()], phase="await_ocr")), WorkflowStep.AWAIT_OCR)
        self.assertEqual(next_step(state([item()], phase="confirm")), WorkflowStep.CONFIRM)

    def test_pending_question_clarifies(self):
        self.assertEqual(next_step(state([item()], pending="which filter?")), WorkflowStep.CLARIFY)

    def test_identify_then_search_then_choose(self):
        self.assertEqual(next_step(state([item(config=None)])), WorkflowStep.IDENTIFY)
        self.assertEqual(next_step(state([item(config=1, candidates=[])])), WorkflowStep.SEARCH)
        self.assertEqual(next_step(state([item(config=1, candidates=[1, 2])])), WorkflowStep.CHOOSE)

    def test_needs_information_clarifies(self):
        self.assertEqual(next_step(state([item(status="needs_information")])), WorkflowStep.CLARIFY)

    def test_tail_plan_draft_verify_review_complete(self):
        ready = [item(status="ready", config=1, candidates=[1], selected=1)]
        self.assertEqual(next_step(state(ready)), WorkflowStep.PLAN)
        self.assertEqual(next_step(state(ready, phase="planned")), WorkflowStep.DRAFT)
        self.assertEqual(next_step(state(ready, phase="planned", draft=uuid4())), WorkflowStep.VERIFY)
        self.assertEqual(
            next_step(state(ready, phase="planned", draft=uuid4(), verification=uuid4())), WorkflowStep.REVIEW
        )
        self.assertEqual(
            next_step(state(ready, phase="approved", draft=uuid4(), verification=uuid4())), WorkflowStep.COMPLETE
        )

    def test_all_unavailable_drafts_explanation(self):
        self.assertEqual(next_step(state([item(status="unavailable")])), WorkflowStep.DRAFT)

    def test_step_cap_needs_staff(self):
        self.assertEqual(next_step(state([item()], step=MAX_STEPS)), WorkflowStep.NEEDS_STAFF)


class GraphExecution(unittest.IsolatedAsyncioTestCase):
    async def test_graph_runs_controller_route_to_review(self):
        async def intake(s):
            return s.model_copy(update={"items": [item(status="ready", config=1, candidates=[1], selected=1)]})

        async def plan(s):
            return s.model_copy(update={"phase": "planned"})

        async def draft(s):
            return s.model_copy(update={"draft_id": uuid4()})

        async def verify(s):
            return s.model_copy(update={"verification_id": uuid4()})

        async def passthrough(s):
            return s

        handlers = WorkflowHandlers(
            intake=intake, identify=passthrough, search=passthrough, choose=passthrough,
            plan=plan, draft=draft, verify=verify,
        )
        graph = build_graph(handlers, InMemorySaver())
        config = {"configurable": {"thread_id": thread_id(uuid4(), 1)}}
        result = await graph.ainvoke(state([]), config)
        final = EnquiryState.model_validate(result)
        self.assertIsNotNone(final.draft_id)
        self.assertIsNotNone(final.verification_id)
        self.assertEqual(next_step(final), WorkflowStep.REVIEW)  # paused awaiting human review


class FakeEventStore:
    def __init__(self, claim, current, run_error=False):
        self._claim = claim
        self._current = current
        self._run_error = run_error
        self.marks = []

    async def claim(self, event_id):
        return self._claim

    async def current(self, enquiry_id):
        return self._current

    async def mark_obsolete(self, event_id):
        self.marks.append("obsolete")

    async def mark_processed(self, event_id):
        self.marks.append("processed")

    async def mark_retry(self, event_id):
        self.marks.append("retry")

    async def run(self, claim):
        if self._run_error:
            raise RuntimeError("handler failed")


class EventConsumption(unittest.IsolatedAsyncioTestCase):
    def _claim(self, revision=1, generation=None):
        return ClaimedEvent(event_id=uuid4(), enquiry_id=uuid4(), revision=revision, session_generation=generation)

    async def test_duplicate_event_is_obsolete(self):
        outcome = await consume_event(uuid4(), store=FakeEventStore(claim=None, current=(1, None)))
        self.assertEqual(outcome.state, "obsolete")

    async def test_stale_revision_is_obsolete(self):
        store = FakeEventStore(claim=self._claim(revision=1), current=(2, None))
        outcome = await consume_event(uuid4(), store=store)
        self.assertEqual(outcome.state, "obsolete")
        self.assertIn("obsolete", store.marks)

    async def test_current_event_processed(self):
        store = FakeEventStore(claim=self._claim(revision=3), current=(3, None))
        outcome = await consume_event(uuid4(), store=store)
        self.assertEqual(outcome.state, "processed")

    async def test_handler_failure_is_retry(self):
        store = FakeEventStore(claim=self._claim(revision=1), current=(1, None), run_error=True)
        outcome = await consume_event(uuid4(), store=store)
        self.assertEqual(outcome.state, "retry")

    async def test_missing_enquiry_failed(self):
        store = FakeEventStore(claim=self._claim(), current=None)
        self.assertEqual((await consume_event(uuid4(), store=store)).state, "failed")


class HandlerReadiness(unittest.TestCase):
    def test_none_registered_is_not_ready(self):
        self.assertFalse(is_ready(None))
        self.assertEqual(len(missing_handlers(None)), 7)


if __name__ == "__main__":
    unittest.main(verbosity=2)
