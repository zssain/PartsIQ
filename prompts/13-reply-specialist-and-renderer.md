# 13 - Reply specialist and renderer
PHASE: Orchestrator   DEPENDS ON: 12   RISK: high

## GOAL
Generate only allowed prose slots with strict schema. Build part/quantity/warehouse/estimate lines in code from verified structured data. Reject identifiers or numeric claims in free prose instead of treating known catalogue membership as sufficient. Escape HTML and render with code-owned layout. Never evaluate model-created Jinja. Staff edits use the same slot schema and rerun verification. Missing AI credit allows staff to author prose while retaining mandatory fact rendering.

## READ FIRST
- AGENTS.md
- docs/HANDOVER.md
- docs/CONSTRAINTS.md
- docs/ARCHITECTURE.md sections 2 and 4
- docs/TECH_SPEC.md
- docs/CONTRACTS.md
- docs/FLOW.md
- spec/file-ownership.json
- features/F45-reply-drafting.md

## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
No new package. Use the existing exact pins and committed locks; do not install a second library for this feature.

## FILES TO CREATE
- `services/orchestrator/app/specialists/reply.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/orchestrator/app/rendering.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/orchestrator/app/prompts/reply.txt`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/orchestrator/tests/features/test_f45.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `tests/foundations/test_13.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.

Typed entry contracts:

async def draft_reply(facts: VerifiedFacts, locale: Locale) -> ReplySlots; def render_reply(slots: ReplySlots, facts: VerifiedFacts, locale: Locale) -> str.

Implementation sequence:
1. Generate only allowed prose slots with strict schema.
2. Build part/quantity/warehouse/estimate lines in code from verified structured data.
3. Reject identifiers or numeric claims in free prose instead of treating known catalogue membership as sufficient.
4. Escape HTML and render with code-owned layout.
5. Never evaluate model-created Jinja.
6. Staff edits use the same slot schema and rerun verification.
7. Missing AI credit allows staff to author prose while retaining mandatory fact rendering.

Required feature behaviours:
- F45 Reply drafting: Generate greeting,explanation and closing as structured slots; code inserts all numbers and allocations; choose Arabic or English from confirmed preference. Failure cases: Unapproved critical facts never rendered; unsupported slots rejected; provider failure permits staff-authored controlled draft.

## FILES TO MODIFY
- `services/orchestrator/app/graph.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.
- `services/orchestrator/app/handlers.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.

## HOW IT CONNECTS
Owner: Orchestrator; ARCHITECTURE.md section2. FLOW.md row `13` identifies the entry contract and preceding owners. Required predecessors: 12. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `services/orchestrator/tests/features/test_f45.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `tests/foundations/test_13.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `F45`: Unapproved critical facts never rendered; unsupported slots rejected; provider failure permits staff-authored controlled draft. Assert generate greeting,explanation and closing as structured slots.

`python tools/run_checks.py --prompt 13` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for reply specialist and renderer using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `13`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-13` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(orchestrator): 13 reply specialist and renderer`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
