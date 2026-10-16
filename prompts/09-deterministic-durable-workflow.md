# 09 - Deterministic durable workflow
PHASE: Orchestrator   DEPENDS ON: 08   RISK: high

## GOAL
Define EnquiryState with items keyed by item UUID,revision,session generation,catalogue version,pending question,draft and verification IDs. Ordered controller rules select intake,await_ocr,confirm,identify,clarify,search,choose,plan,draft,verify,review,complete or needs_staff. Persist interrupts. Register handler interfaces and inject test doubles in tests; do not ship runnable fake-success nodes. Start/resume endpoints enqueue idempotent DB events. Consumer claims events under lease and locks enquiry; after each stage verify revision/session still current. Checkpointer migrations run only in 03.

## READ FIRST
- AGENTS.md
- docs/HANDOVER.md
- docs/CONSTRAINTS.md
- docs/ARCHITECTURE.md sections 2 and 4
- docs/TECH_SPEC.md
- docs/CONTRACTS.md
- docs/FLOW.md
- spec/file-ownership.json
- features/F10-structured-extraction.md
- features/F11-clarifying-questions.md
- features/F12-conversation-memory.md
- features/F18-progress-timeline.md
- features/F50-durable-workflows.md
- features/F67-traces.md

## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
- `uv pip install langgraph==1.1.3 langgraph-checkpoint-postgres==3.0.4` in the task-specific development environment. Add the identical pins to the owning workspace project; synchronize from the shared workspace lock for application execution.

Release dates and registry receipts are in spec/dependency-receipts.json. Use spec/python-requirements.lock and spec/pnpm-lock.yaml as resolution references; do not claim installing these packages proves application compatibility.

## FILES TO CREATE
- `services/orchestrator/app/main.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/orchestrator/app/state.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/orchestrator/app/controller.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/orchestrator/app/graph.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/orchestrator/app/events.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/orchestrator/app/routes.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/orchestrator/app/handlers.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/orchestrator/app/runner.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/orchestrator/tests/features/test_f12.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `services/orchestrator/tests/features/test_f50.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `tests/foundations/test_09.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.

Typed entry contracts:

def next_step(state: EnquiryState) -> WorkflowStep; def build_graph(handlers: WorkflowHandlers, checkpointer: AsyncPostgresSaver) -> CompiledStateGraph; async def consume_event(event_id: UUID) -> EventOutcome.

Implementation sequence:
1. Define EnquiryState with items keyed by item UUID,revision,session generation,catalogue version,pending question,draft and verification IDs.
2. Ordered controller rules select intake,await_ocr,confirm,identify,clarify,search,choose,plan,draft,verify,review,complete or needs_staff.
3. Persist interrupts.
4. Register handler interfaces and inject test doubles in tests; do not ship runnable fake-success nodes.
5. Start/resume endpoints enqueue idempotent DB events.
6. Consumer claims events under lease and locks enquiry; after each stage verify revision/session still current.
7. Checkpointer migrations run only in 03.

Required feature behaviours:
- F10 Structured extraction: Extract item descriptions, quantities, urgency and machine hints with strict structured outputs; preserve source spans; missing quantity becomes a clarification rather than assumed order quantity. Failure cases: Unknown keys and invalid quantities reject the response; unsupported model output cannot progress to search.
- F11 Clarifying questions: Use controller reason codes to choose code-owned bilingual questions; persist interrupt; associate answer with item; rerun affected resolution only. Failure cases: No final recommendation before approval; contradictory answer requires confirmation; repeat event creates one question.
- F12 Conversation memory: Persist all messages and typed current state; compact context using retained structured facts; resume by enquiry/revision; never mix customer sessions. Failure cases: Restart retains unresolved questions; old revision events are ignored and audited; foreign thread ID denied.
- F18 Progress timeline: Show persisted stages, wait reason and last update; poll with bounded backoff; reconnect using server state; separate waiting for customer from waiting for staff. Failure cases: No fake completed progress; failed poll retains last state and offers retry; hidden tabs reduce polling.
- F50 Durable workflows: Use Postgres checkpointer and DB event inbox; thread key includes enquiry ID and active revision; serialize processing for one enquiry; recover after restart. Failure cases: Duplicate events do not repeat publication; stale revision event is consumed as obsolete; checkpoint DDL never runs under runtime role.
- F67 Traces: Propagate request/enquiry/job IDs; capture stage timing and safe status; export optional Langfuse traces with payload redaction; operate normally when tracing unavailable. Failure cases: No raw key or full photo logged; exporter outage never breaks approval; budget accounting remains local and authoritative.

Exact package markers and bundled assets created by this step:
- `services/orchestrator/app/__init__.py`

## FILES TO MODIFY
No existing runtime file requires modification beyond the documentation updates and package manifests named here.

## HOW IT CONNECTS
Owner: Orchestrator; ARCHITECTURE.md section2. FLOW.md row `09` identifies the entry contract and preceding owners. Required predecessors: 08. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `services/orchestrator/tests/features/test_f12.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `services/orchestrator/tests/features/test_f50.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `tests/foundations/test_09.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `F10`: Unknown keys and invalid quantities reject the response; unsupported model output cannot progress to search. Assert extract item descriptions, quantities, urgency and machine hints with strict structured outputs.
- `F11`: No final recommendation before approval; contradictory answer requires confirmation; repeat event creates one question. Assert use controller reason codes to choose code-owned bilingual questions.
- `F12`: Restart retains unresolved questions; old revision events are ignored and audited; foreign thread ID denied. Assert persist all messages and typed current state.
- `F18`: No fake completed progress; failed poll retains last state and offers retry; hidden tabs reduce polling. Assert show persisted stages, wait reason and last update.
- `F50`: Duplicate events do not repeat publication; stale revision event is consumed as obsolete; checkpoint DDL never runs under runtime role. Assert use postgres checkpointer and db event inbox.
- `F67`: No raw key or full photo logged; exporter outage never breaks approval; budget accounting remains local and authoritative. Assert propagate request/enquiry/job ids.

`python tools/run_checks.py --prompt 09` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for deterministic durable workflow using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `09`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-09` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(orchestrator): 09 deterministic durable workflow`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
