# 10 - Intake specialist
PHASE: Orchestrator   DEPENDS ON: 09   RISK: high

## GOAL
Use shared OpenAI structured-output wrapper with IntakeResult schema. Send customer input in data field, preserve source spans, extract up to20 items. The model proposes quantities explicitly mentioned by customer; code validates positive units and asks when absent. Disallow status,approval,stock and compatibility fields. Detect change intent and compare against confirmed state. Store extracted proposals only after schema validation; confirmed machine fields are not silently overwritten.

## READ FIRST
- AGENTS.md
- docs/HANDOVER.md
- docs/CONSTRAINTS.md
- docs/ARCHITECTURE.md sections 2 and 4
- docs/TECH_SPEC.md
- docs/CONTRACTS.md
- docs/FLOW.md
- spec/file-ownership.json
- features/F09-bilingual-chat.md
- features/F10-structured-extraction.md

## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
No new package. Use the existing exact pins and committed locks; do not install a second library for this feature.

## FILES TO CREATE
- `services/orchestrator/app/specialists/intake.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/orchestrator/app/prompts/intake.txt`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/orchestrator/tests/features/test_f10.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `tests/foundations/test_10.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.

Typed entry contracts:

async def extract_intake(messages: list[MessageView], previous: IntakeResult | None, actor: ActorContext) -> IntakeResult.

Implementation sequence:
1. Use shared OpenAI structured-output wrapper with IntakeResult schema.
2. Send customer input in data field, preserve source spans, extract up to20 items.
3. The model proposes quantities explicitly mentioned by customer; code validates positive units and asks when absent.
4. Disallow status,approval,stock and compatibility fields.
5. Detect change intent and compare against confirmed state.
6. Store extracted proposals only after schema validation; confirmed machine fields are not silently overwritten.

Required feature behaviours:
- F09 Bilingual chat: Accept Arabic, English and mixed text; preserve original message; detect preferred reply locale; render customer messages immediately after successful persistence. Failure cases: Empty and oversized input returns validation error; HTML is escaped; retry does not duplicate a message.
- F10 Structured extraction: Extract item descriptions, quantities, urgency and machine hints with strict structured outputs; preserve source spans; missing quantity becomes a clarification rather than assumed order quantity. Failure cases: Unknown keys and invalid quantities reject the response; unsupported model output cannot progress to search.

Exact package markers and bundled assets created by this step:
- `services/orchestrator/app/specialists/__init__.py`

## FILES TO MODIFY
- `services/orchestrator/app/graph.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.
- `services/orchestrator/app/handlers.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.

## HOW IT CONNECTS
Owner: Orchestrator; ARCHITECTURE.md section2. FLOW.md row `10` identifies the entry contract and preceding owners. Required predecessors: 09. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `services/orchestrator/tests/features/test_f10.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `tests/foundations/test_10.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `F09`: Empty and oversized input returns validation error; HTML is escaped; retry does not duplicate a message. Assert accept arabic, english and mixed text.
- `F10`: Unknown keys and invalid quantities reject the response; unsupported model output cannot progress to search. Assert extract item descriptions, quantities, urgency and machine hints with strict structured outputs.

`python tools/run_checks.py --prompt 10` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for intake specialist using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `10`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-10` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(orchestrator): 10 intake specialist`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
