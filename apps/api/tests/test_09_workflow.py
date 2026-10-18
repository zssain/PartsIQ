"""Foundation 09 acceptance: the durable workflow transition table + step primitive.

Fully offline and deterministic. The transition table is a pure function of the typed state, so
an LLM is NEVER consulted to pick the next step (asserted explicitly). The step primitive
(``run_next``) is exercised with injected test-double handlers and the in-memory fenced
repository. Live PostgreSQL persistence (workflow_runs / workflow_step_results) is BLOCKED and
reported — no live-DB test is faked.

Architecture note: the AUTHORITATIVE workflow engine is LangGraph (``partsiq.workflow.graph`` +
a Postgres/InMemory checkpointer; see ``test_workflow_langgraph.py``). The deterministic router
(``transitions.next_step``) and ``state`` stay pure and langgraph-free so routing is code, never a
model; the graph reuses that router verbatim. ``run_next`` remains the fenced, de-duplicated
step-outcome primitive the staff timeline and the no-replay guarantee read from.
"""
from __future__ import annotations

import unittest
from uuid import uuid4

from partsiq.core.api_models import ExtractionContext, StepOutcome
from partsiq.core.contracts import (
    EnquiryState,
    ItemInput,
    ItemState,
    MessageView,
    WorkflowStep,
)
from partsiq.workflow.repository import (
    InMemoryWorkflowRepository,
    RecordedStep,
    WorkflowFence,
)
from partsiq.workflow.runner import (
    REQUIRED_HANDLERS,
    RunStatus,
    StepHandlers,
    canonical_input_hash,
    is_ready,
    missing_handlers,
    run_next,
)
from partsiq.workflow.state import (
    advance,
    carry_forward_memory,
    new_state,
    reset_derived_state,
    thread_id,
)
from partsiq.workflow.transitions import (
    ALLOWED_TRANSITIONS,
    MAX_STEPS,
    next_step,
)


# --------------------------------------------------------------------------- builders


def item(status="unresolved", *, config=None, candidates=(), selected=None, iid=None):
    return ItemState(
        id=iid or uuid4(),
        request=ItemInput(
            description="oil filter", source_message_id=uuid4(), source_start=0, source_end=3
        ),
        configuration_id=config,
        candidate_part_ids=list(candidates),
        selected_part_id=selected,
        status=status,
    )


def state(
    items=None,
    *,
    step=0,
    phase="",
    pending=None,
    draft=None,
    verification=None,
    rev=1,
    gen=None,
    enquiry_id=None,
):
    return EnquiryState(
        enquiry_id=enquiry_id or uuid4(),
        revision=rev,
        session_generation=gen,
        catalogue_version_id=None,
        items=items if items is not None else [],
        step_count=step,
        pending_question=pending,
        draft_id=draft,
        verification_id=verification,
        phase=phase,
    )


# --------------------------------------------------------------------------- transition table


class TransitionTable(unittest.TestCase):
    """Every journey edge in docs/WORKFLOW.md, expressed and asserted as pure Python."""

    def test_empty_items_intake(self):
        self.assertEqual(next_step(state([])), WorkflowStep.INTAKE)

    def test_intake_to_await_ocr_then_confirm(self):
        # intake -> await_ocr (validated image needs reading), await_ocr -> confirm.
        self.assertEqual(next_step(state([item()], phase="await_ocr")), WorkflowStep.AWAIT_OCR)
        self.assertEqual(next_step(state([item()], phase="confirm")), WorkflowStep.CONFIRM)

    def test_pending_question_clarifies(self):
        self.assertEqual(
            next_step(state([item()], pending="fuel filter or separator?")), WorkflowStep.CLARIFY
        )

    def test_needs_information_clarifies(self):
        self.assertEqual(
            next_step(state([item(status="needs_information")])), WorkflowStep.CLARIFY
        )

    def test_identify_search_choose(self):
        self.assertEqual(next_step(state([item(config=None)])), WorkflowStep.IDENTIFY)
        self.assertEqual(next_step(state([item(config=1, candidates=[])])), WorkflowStep.SEARCH)
        self.assertEqual(
            next_step(state([item(config=1, candidates=[1, 2])])), WorkflowStep.CHOOSE
        )

    def test_configured_undecidable_needs_staff(self):
        # search found exactly one candidate yet the item is still 'unresolved' (not selectable
        # automatically): escalate rather than guess.
        self.assertEqual(
            next_step(state([item(config=1, candidates=[9], selected=None)])),
            WorkflowStep.NEEDS_STAFF,
        )

    def test_full_tail_plan_draft_verify_review_complete(self):
        ready = [item(status="ready", config=1, candidates=[1], selected=1)]
        self.assertEqual(next_step(state(ready)), WorkflowStep.PLAN)
        self.assertEqual(next_step(state(ready, phase="planned")), WorkflowStep.DRAFT)
        self.assertEqual(
            next_step(state(ready, phase="planned", draft=uuid4())), WorkflowStep.VERIFY
        )
        self.assertEqual(
            next_step(state(ready, phase="planned", draft=uuid4(), verification=uuid4())),
            WorkflowStep.REVIEW,
        )
        self.assertEqual(
            next_step(state(ready, phase="approved", draft=uuid4(), verification=uuid4())),
            WorkflowStep.COMPLETE,
        )

    def test_all_unavailable_still_drafts_explanation(self):
        # Nothing ready to plan: skip plan and draft the unavailable explanation.
        self.assertEqual(next_step(state([item(status="unavailable")])), WorkflowStep.DRAFT)

    def test_step_cap_escalates_to_staff(self):
        self.assertEqual(next_step(state([item()], step=MAX_STEPS)), WorkflowStep.NEEDS_STAFF)

    def test_first_unresolved_item_drives_step_multi_part(self):
        # F17: with several items, the first non-terminal item decides the step; a resolved
        # item does not mask an unresolved one.
        items = [
            item(status="ready", config=1, candidates=[1], selected=1),
            item(config=None),
        ]
        self.assertEqual(next_step(state(items)), WorkflowStep.IDENTIFY)

    def test_every_computed_transition_is_a_declared_edge(self):
        # For each edge, construct the state that RESULTS once the ``current`` step's outcome
        # has been applied, then assert next_step yields the declared onward ``next``. This
        # proves next_step only ever produces edges in the fixed table — no undeclared jump.
        did, vid = uuid4(), uuid4()
        ready = [item(status="ready", config=1, candidates=[1], selected=1)]
        cases: list[tuple[WorkflowStep, WorkflowStep, EnquiryState]] = [
            # intake outcomes
            (WorkflowStep.INTAKE, WorkflowStep.IDENTIFY, state([item(config=None)])),
            (WorkflowStep.INTAKE, WorkflowStep.CLARIFY, state([item()], pending="q?")),
            (WorkflowStep.INTAKE, WorkflowStep.AWAIT_OCR, state([item()], phase="await_ocr")),
            # await_ocr outcome: OCR persisted -> the enquiry now rests in 'confirm'.
            (WorkflowStep.AWAIT_OCR, WorkflowStep.CONFIRM, state([item()], phase="confirm")),
            # confirm outcome: identifiers confirmed -> item back to unresolved, needs identify.
            (WorkflowStep.CONFIRM, WorkflowStep.IDENTIFY, state([item(config=None)])),
            # identify outcomes
            (WorkflowStep.IDENTIFY, WorkflowStep.SEARCH, state([item(config=1, candidates=[])])),
            (WorkflowStep.IDENTIFY, WorkflowStep.CLARIFY, state([item(status="needs_information")])),
            # clarify outcome: a new answer re-enters at identify.
            (WorkflowStep.CLARIFY, WorkflowStep.IDENTIFY, state([item(config=None)])),
            # search outcomes
            (WorkflowStep.SEARCH, WorkflowStep.CHOOSE, state([item(config=1, candidates=[1, 2])])),
            (WorkflowStep.SEARCH, WorkflowStep.PLAN, state(ready)),
            (WorkflowStep.SEARCH, WorkflowStep.NEEDS_STAFF, state([item(config=1, candidates=[9])])),
            # choose outcome: selected -> plan.
            (WorkflowStep.CHOOSE, WorkflowStep.PLAN, state(ready)),
            # plan outcome
            (WorkflowStep.PLAN, WorkflowStep.DRAFT, state(ready, phase="planned")),
            (WorkflowStep.PLAN, WorkflowStep.NEEDS_STAFF, state(ready, step=MAX_STEPS)),
            # draft outcome -> verify.
            (WorkflowStep.DRAFT, WorkflowStep.VERIFY, state(ready, phase="planned", draft=did)),
            # verify outcomes
            (
                WorkflowStep.VERIFY,
                WorkflowStep.REVIEW,
                state(ready, phase="verified", draft=did, verification=vid),
            ),
            (WorkflowStep.VERIFY, WorkflowStep.NEEDS_STAFF, state(ready, step=MAX_STEPS)),
            # review outcome: approved -> complete.
            (
                WorkflowStep.REVIEW,
                WorkflowStep.COMPLETE,
                state(ready, phase="approved", draft=did, verification=vid),
            ),
        ]
        for current, expected_next, st in cases:
            nxt = next_step(st)
            self.assertEqual(nxt, expected_next, msg=f"{current.value} -> expected {expected_next.value}")
            self.assertIn(
                (current, nxt),
                ALLOWED_TRANSITIONS,
                msg=f"undeclared edge {current.value} -> {nxt.value}",
            )


class DeterminismNoLLM(unittest.TestCase):
    """The transition is a pure, deterministic function of state — no model is consulted."""

    def test_pure_router_and_state_import_no_llm_or_langgraph(self):
        # The AUTHORITATIVE engine is LangGraph (partsiq.workflow.graph), but the deterministic
        # ROUTER and STATE must stay pure: their source imports no langgraph, no LLM and no
        # network client, so routing can never be steered by a model or a provider call. A static
        # AST check (not a runtime sys.modules reload, which would corrupt other tests).
        import ast
        import inspect

        import partsiq.workflow.state as state_mod
        import partsiq.workflow.transitions as transitions_mod

        for mod in (transitions_mod, state_mod):
            tree = ast.parse(inspect.getsource(mod))
            imported: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
            for forbidden in ("langgraph", "langchain", "openai", "httpx", "requests", "asyncpg"):
                self.assertNotIn(forbidden, imported, f"{mod.__name__} must not import {forbidden}")

    def test_next_step_is_pure_and_repeatable(self):
        st = state([item(config=1, candidates=[1, 2])])
        results = {next_step(st) for _ in range(50)}
        self.assertEqual(results, {WorkflowStep.CHOOSE})  # same input -> one deterministic output

    def test_transitions_module_imports_no_io(self):
        # The pure transition module must not import a provider/db/network/agent client.
        # Inspect actual import statements (not docstrings/comments, which legitimately name
        # langgraph to record that it is deliberately absent).
        import ast
        import inspect

        import partsiq.workflow.transitions as mod

        tree = ast.parse(inspect.getsource(mod))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        for forbidden in ("openai", "httpx", "asyncpg", "langgraph", "langchain", "requests"):
            self.assertNotIn(forbidden, imported)


# --------------------------------------------------------------------------- state / memory


class StateAndMemory(unittest.TestCase):
    def test_thread_key_per_enquiry_and_revision(self):
        enq = uuid4()
        self.assertNotEqual(thread_id(enq, 1), thread_id(enq, 2))
        self.assertIn(str(enq), thread_id(enq, 1))
        self.assertTrue(thread_id(enq, 3).endswith(":rev:3"))

    def test_new_state_and_advance(self):
        st = new_state(uuid4(), 1)
        self.assertEqual(st.step_count, 0)
        self.assertEqual(advance(st).step_count, 1)
        self.assertEqual(st.step_count, 0)  # original unchanged (immutable copy)

    def test_reset_derived_state_clears_only_derived(self):
        st = state(
            [item(status="ready", config=1, candidates=[1], selected=1)],
            phase="approved",
            draft=uuid4(),
            verification=uuid4(),
            pending="q?",
        )
        reset = reset_derived_state(st)
        self.assertIsNone(reset.draft_id)
        self.assertIsNone(reset.verification_id)
        self.assertIsNone(reset.pending_question)
        self.assertEqual(reset.phase, "intake")
        self.assertEqual(reset.items, st.items)  # facts/items preserved

    # F12 conversation memory -----------------------------------------------------------

    def _msg(self, enquiry_id, body="air filter"):
        return MessageView(
            id=uuid4(),
            enquiry_id=enquiry_id,
            revision=1,
            kind="customer",
            body=body,
            created_at=__import__("datetime").datetime(
                2026, 10, 17, tzinfo=__import__("datetime").timezone.utc
            ),
        )

    def test_memory_carries_confirmed_facts_and_messages_forward(self):
        st = state([item()])
        messages = [self._msg(st.enquiry_id, "need a filter"), self._msg(st.enquiry_id, "urgent")]
        ctx = carry_forward_memory(
            st, messages, confirmed_model="CAT-320D", confirmed_serial="00042"
        )
        self.assertIsInstance(ctx, ExtractionContext)
        self.assertEqual(ctx.enquiry_id, st.enquiry_id)
        self.assertEqual(ctx.revision, st.revision)
        self.assertEqual(len(ctx.messages), 2)  # full history retained
        self.assertEqual(ctx.confirmed_model, "CAT-320D")  # confirmed fact carried forward
        self.assertEqual(ctx.confirmed_serial, "00042")  # leading zero preserved

    def test_memory_never_mixes_a_foreign_thread(self):
        st = state([item()])
        foreign = self._msg(uuid4(), "another customer's message")
        mine = self._msg(st.enquiry_id, "my message")
        ctx = carry_forward_memory(st, [foreign, mine])
        self.assertEqual([m.body for m in ctx.messages], ["my message"])  # foreign dropped


# --------------------------------------------------------------------------- runner loop


async def _handler(updates, reason=None):
    async def handler(_state):
        return (updates, reason)

    return handler


class RunnerLoop(unittest.IsolatedAsyncioTestCase):
    def _prepared(self, items, *, rev=1, gen=None):
        enq = uuid4()
        lease = uuid4()
        st = state(items, rev=rev, gen=gen, enquiry_id=enq)
        repo = InMemoryWorkflowRepository()
        repo.set_current(enq, rev, gen)
        repo.set_lease(enq, lease)
        return st, repo, lease

    async def test_runs_one_step_and_advances(self):
        st, repo, lease = self._prepared([item(config=1, candidates=[])])

        async def search(_s):
            return ({"items": [item(status="ready", config=1, candidates=[5], selected=5)]}, "unique")

        res = await run_next(st, StepHandlers(search=search), repo, lease_token=lease)
        self.assertEqual(res.status, RunStatus.ADVANCED)
        self.assertEqual(res.step, WorkflowStep.SEARCH)
        self.assertEqual(res.state.step_count, 1)
        self.assertEqual(res.state.items[0].status, "ready")
        # Exactly one StepOutcome persisted for this step.
        recorded = await repo.load_recorded(st.enquiry_id, st.revision, WorkflowStep.SEARCH)
        self.assertIsNotNone(recorded)
        self.assertEqual(recorded.outcome.reason_code, "unique")

    async def test_waiting_step_suspends_without_calling_a_handler(self):
        st, repo, lease = self._prepared([item()])
        st = st.model_copy(update={"phase": "await_ocr"})

        async def never(_s):  # pragma: no cover - must not be called
            raise AssertionError("handler called for a waiting step")

        res = await run_next(st, StepHandlers(intake=never), repo, lease_token=lease)
        self.assertEqual(res.status, RunStatus.WAITING)
        self.assertEqual(res.step, WorkflowStep.AWAIT_OCR)
        self.assertEqual(res.state.step_count, 0)  # no step consumed

    async def test_review_waits_and_needs_staff_is_terminal(self):
        ready = [item(status="ready", config=1, candidates=[1], selected=1)]
        st, repo, lease = self._prepared(ready)
        st = st.model_copy(update={"draft_id": uuid4(), "verification_id": uuid4(), "phase": "planned"})
        res = await run_next(st, StepHandlers(), repo, lease_token=lease)
        self.assertEqual(res.status, RunStatus.WAITING)
        self.assertEqual(res.step, WorkflowStep.REVIEW)

        st2, repo2, lease2 = self._prepared([item()], rev=1)
        st2 = st2.model_copy(update={"step_count": MAX_STEPS})  # forces needs_staff
        res2 = await run_next(st2, StepHandlers(), repo2, lease_token=lease2)
        self.assertEqual(res2.status, RunStatus.TERMINAL)
        self.assertEqual(res2.step, WorkflowStep.NEEDS_STAFF)

    # F50 durable resume ----------------------------------------------------------------

    async def test_completed_step_replays_as_no_op(self):
        st, repo, lease = self._prepared([item(config=1, candidates=[])])
        calls = {"n": 0}

        async def search(_s):
            calls["n"] += 1
            return ({"items": [item(status="ready", config=1, candidates=[5], selected=5)]}, "unique")

        handlers = StepHandlers(search=search)
        first = await run_next(st, handlers, repo, lease_token=lease)
        self.assertEqual(first.status, RunStatus.ADVANCED)
        # Re-run the SAME starting state: the committed result is replayed, handler not called.
        second = await run_next(st, handlers, repo, lease_token=lease)
        self.assertEqual(second.status, RunStatus.REPLAYED)
        self.assertEqual(calls["n"], 1)  # handler executed exactly once
        self.assertEqual(second.state.items[0].status, "ready")  # resumed from committed result

    async def test_input_hash_depends_on_revision_and_step(self):
        st = state([item(config=1, candidates=[])])
        h_search = canonical_input_hash(st, WorkflowStep.SEARCH)
        h_identify = canonical_input_hash(st, WorkflowStep.IDENTIFY)
        h_rev2 = canonical_input_hash(st.model_copy(update={"revision": 2}), WorkflowStep.SEARCH)
        self.assertNotEqual(h_search, h_identify)
        self.assertNotEqual(h_search, h_rev2)
        self.assertEqual(h_search, canonical_input_hash(st, WorkflowStep.SEARCH))  # stable

    # F50 fencing -----------------------------------------------------------------------

    async def test_stale_revision_commit_is_discarded(self):
        st, repo, lease = self._prepared([item(config=1, candidates=[])], rev=1)
        repo.set_current(st.enquiry_id, 2, None)  # a correction advanced the enquiry to rev 2

        async def search(_s):
            return ({"items": [item(status="ready", config=1, candidates=[5], selected=5)]}, "unique")

        res = await run_next(st, StepHandlers(search=search), repo, lease_token=lease)
        self.assertEqual(res.status, RunStatus.FENCED)
        self.assertEqual(res.state.step_count, 0)  # did not advance
        self.assertIsNone(await repo.load_recorded(st.enquiry_id, 1, WorkflowStep.SEARCH))
        self.assertEqual(len(repo.discarded), 1)  # discarded result audited, not silently lost

    async def test_old_session_generation_commit_is_discarded(self):
        st, repo, lease = self._prepared([item(config=1, candidates=[])], rev=1, gen=1)
        repo.set_current(st.enquiry_id, 1, 2)  # a demo reset bumped generation to 2

        async def search(_s):
            return ({"items": [item(status="ready", config=1, candidates=[5], selected=5)]}, "unique")

        res = await run_next(st, StepHandlers(search=search), repo, lease_token=lease)
        self.assertEqual(res.status, RunStatus.FENCED)
        self.assertEqual(len(repo.discarded), 1)

    async def test_expired_lease_commit_is_discarded(self):
        st, repo, lease = self._prepared([item(config=1, candidates=[])])
        repo.set_lease(st.enquiry_id, uuid4())  # the lease was reclaimed by another worker

        async def search(_s):
            return ({"items": [item(status="ready", config=1, candidates=[5], selected=5)]}, "unique")

        res = await run_next(st, StepHandlers(search=search), repo, lease_token=lease)
        self.assertEqual(res.status, RunStatus.FENCED)

    async def test_fresh_fence_commits(self):
        st, repo, lease = self._prepared([item(config=1, candidates=[])], rev=3, gen=4)

        async def search(_s):
            return ({"items": [item(status="ready", config=1, candidates=[5], selected=5)]}, "unique")

        res = await run_next(st, StepHandlers(search=search), repo, lease_token=lease)
        self.assertEqual(res.status, RunStatus.ADVANCED)

    async def test_driving_the_full_journey_to_review(self):
        # The plain loop walks intake->...->review purely via next_step; no LLM routes it.
        enq = uuid4()
        lease = uuid4()
        repo = InMemoryWorkflowRepository()
        repo.set_current(enq, 1, None)
        repo.set_lease(enq, lease)
        st = state([], enquiry_id=enq)

        ready = [item(status="ready", config=1, candidates=[1], selected=1)]

        async def intake(_s):
            return ({"items": ready}, "extracted")

        async def plan(_s):
            return ({"phase": "planned"}, "planned")

        async def draft(_s):
            return ({"draft_id": uuid4(), "phase": "drafted"}, "drafted")

        async def verify(_s):
            return ({"verification_id": uuid4(), "phase": "verified"}, "passed")

        handlers = StepHandlers(intake=intake, plan=plan, draft=draft, verify=verify)
        seen: list[WorkflowStep] = []
        for _ in range(20):
            res = await run_next(st, handlers, repo, lease_token=lease)
            seen.append(res.step)
            st = res.state
            if res.status in (RunStatus.WAITING, RunStatus.TERMINAL, RunStatus.FENCED):
                break
        self.assertEqual(
            seen,
            [
                WorkflowStep.INTAKE,
                WorkflowStep.PLAN,
                WorkflowStep.DRAFT,
                WorkflowStep.VERIFY,
                WorkflowStep.REVIEW,
            ],
        )
        self.assertIsNotNone(st.draft_id)
        self.assertIsNotNone(st.verification_id)
        self.assertEqual(next_step(st), WorkflowStep.REVIEW)  # paused awaiting human review


# --------------------------------------------------------------------------- readiness / repo


class HandlerReadiness(unittest.TestCase):
    def test_no_handlers_is_not_ready(self):
        self.assertFalse(is_ready(None))
        self.assertEqual(len(missing_handlers(None)), 7)
        self.assertEqual(set(REQUIRED_HANDLERS), {"intake", "identify", "search", "choose", "plan", "draft", "verify"})

    def test_partial_registration_reports_the_gaps(self):
        async def h(_s):
            return ({}, None)

        handlers = StepHandlers(intake=h, identify=h)
        self.assertFalse(is_ready(handlers))
        self.assertEqual(set(missing_handlers(handlers)), {"search", "choose", "plan", "draft", "verify"})


class RepositoryContract(unittest.IsolatedAsyncioTestCase):
    async def test_idempotent_recommit_of_same_step_is_accepted(self):
        enq = uuid4()
        lease = uuid4()
        repo = InMemoryWorkflowRepository()
        repo.set_current(enq, 1, None)
        repo.set_lease(enq, lease)
        fence = WorkflowFence(enquiry_id=enq, revision=1, session_generation=None, lease_token=lease)
        outcome = StepOutcome(step=WorkflowStep.VERIFY, reason_code="passed", data={"phase": "verified"})
        self.assertTrue(await repo.commit_step(fence, WorkflowStep.VERIFY, "hash-1", outcome))
        # Same (step, input_hash) committed again: accepted as a durable no-op.
        self.assertTrue(await repo.commit_step(fence, WorkflowStep.VERIFY, "hash-1", outcome))
        recorded = await repo.load_recorded(enq, 1, WorkflowStep.VERIFY)
        self.assertIsInstance(recorded, RecordedStep)

    async def test_current_fence_reports_revision_and_generation(self):
        enq = uuid4()
        repo = InMemoryWorkflowRepository()
        repo.set_current(enq, 7, 3)
        self.assertEqual(await repo.current_fence(enq), (7, 3))
        self.assertIsNone(await repo.current_fence(uuid4()))


# --------------------------------------------------------------------------- blocked (live DB)


class LivePersistence(unittest.IsolatedAsyncioTestCase):
    @unittest.skip(
        "workflow_runs/workflow_step_results DDL + fenced commits require a live PostgreSQL "
        "(foundation 03); integration-only and BLOCKED here"
    )
    async def test_asyncpg_repository_fenced_commit(self):  # pragma: no cover
        raise AssertionError("must not run without a live DB")


if __name__ == "__main__":
    unittest.main(verbosity=2)
