# 11 - Parts specialist and tools
PHASE: Orchestrator   DEPENDS ON: 10   RISK: high

## GOAL
Register only identify,search_parts,part_detail and plan_fulfilment tools with typed arguments and fixed internal URL. Deterministic code identifies configuration and restricts candidate IDs. LLM may explain or propose clarification using those results; it cannot select incompatible parts or change quantities. Limit to four tool calls per stage and twelve graph transitions before needs_staff. Validate response catalogue version,request correlation and item ID; reject stale version.

## READ FIRST
- AGENTS.md
- docs/HANDOVER.md
- docs/CONSTRAINTS.md
- docs/ARCHITECTURE.md sections 2 and 4
- docs/TECH_SPEC.md
- docs/CONTRACTS.md
- docs/FLOW.md
- spec/file-ownership.json
- features/F11-clarifying-questions.md
- features/F26-ambiguity-handling.md

## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
No new package. Use the existing exact pins and committed locks; do not install a second library for this feature.

## FILES TO CREATE
- `services/orchestrator/app/specialists/parts.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/orchestrator/app/tools.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/orchestrator/app/search_client.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/orchestrator/tests/features/test_f26.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `tests/foundations/test_11.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.

Typed entry contracts:

async def run_parts(item: ItemState, context: ToolContext) -> PartsProposal; async def identify(request: IdentifyRequest) -> IdentifyResponse; async def search_parts(request: PartSearchRequest) -> PartSearchResponse; async def plan_fulfilment(request: FulfilmentRequest) -> FulfilmentResponse.

Implementation sequence:
1. Register only identify,search_parts,part_detail and plan_fulfilment tools with typed arguments and fixed internal URL.
2. Deterministic code identifies configuration and restricts candidate IDs.
3. LLM may explain or propose clarification using those results; it cannot select incompatible parts or change quantities.
4. Limit to four tool calls per stage and twelve graph transitions before needs_staff.
5. Validate response catalogue version,request correlation and item ID; reject stale version.

Required feature behaviours:
- F11 Clarifying questions: Use controller reason codes to choose code-owned bilingual questions; persist interrupt; associate answer with item; rerun affected resolution only. Failure cases: No final recommendation before approval; contradictory answer requires confirmation; repeat event creates one question.
- F26 Ambiguity handling: Use tested score and margin thresholds in code; ask customer to distinguish fuel filter versus separator; allow staff to select only verified candidates. Failure cases: LLM cannot override low confidence; unavailable candidate choice returns 409; thresholds evaluated on labelled cases.

## FILES TO MODIFY
- `services/orchestrator/app/graph.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.
- `services/orchestrator/app/handlers.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.

## HOW IT CONNECTS
Owner: Orchestrator; ARCHITECTURE.md section2. FLOW.md row `11` identifies the entry contract and preceding owners. Required predecessors: 10. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `services/orchestrator/tests/features/test_f26.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `tests/foundations/test_11.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `F11`: No final recommendation before approval; contradictory answer requires confirmation; repeat event creates one question. Assert use controller reason codes to choose code-owned bilingual questions.
- `F26`: LLM cannot override low confidence; unavailable candidate choice returns 409; thresholds evaluated on labelled cases. Assert use tested score and margin thresholds in code.

`python tools/run_checks.py --prompt 11` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for parts specialist and tools using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `11`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-11` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(orchestrator): 11 parts specialist and tools`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
