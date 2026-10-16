# F69 - Demo walkthrough
PHASE: docs   DEPENDS ON: 27, F68   RISK: high

## GOAL
Create 3-minute and 8-minute scripts covering happy path,missing serial,incompatibility,stock split and human review; include recording checklist and captions. Do not claim video exists until recorded; use synthetic data; show failure handling and reset; verify links before sending recruiters.

## READ FIRST
- AGENTS.md
- docs/HANDOVER.md
- docs/CONSTRAINTS.md
- docs/ARCHITECTURE.md sections 2 and 4
- docs/TECH_SPEC.md
- docs/CONTRACTS.md
- docs/FLOW.md
- spec/file-ownership.json
- features/F69-demo-walkthrough.md

## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
No new package. Use the existing exact pins and committed locks; do not install a second library for this feature.

## FILES TO CREATE
- `tests/acceptance/test_f69.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `docs/DEMO_SCRIPT.md`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `docs/RECORDING_CHECKLIST.md`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.

Typed entry contracts:

Documentation contract: docs/DEMO_SCRIPT.md and docs/RECORDING_CHECKLIST.md

`F69Request`: source: four verified demo scenarios.

`F69Result`: docs/DEMO_SCRIPT.md and docs/RECORDING_CHECKLIST.md.

Endpoint: `none`. For a public route whose owner is worker/catalogue, gateway validates role and records a durable job/event; it never executes the job inline. Internal routes use the internal token and propagated actor context.

Implementation sequence:
1. Create 3-minute and 8-minute scripts covering happy path,missing serial,incompatibility,stock split and human review; include recording checklist and captions.
2. Do not claim video exists until recorded; use synthetic data; show failure handling and reset; verify links before sending recruiters.

Required feature behaviours:
- F69 Demo walkthrough: Create 3-minute and 8-minute scripts covering happy path,missing serial,incompatibility,stock split and human review; include recording checklist and captions. Failure cases: Do not claim video exists until recorded; use synthetic data; show failure handling and reset; verify links before sending recruiters.

## FILES TO MODIFY
No existing runtime file requires modification beyond the documentation updates and package manifests named here.

## HOW IT CONNECTS
Owner: docs; ARCHITECTURE.md section2. FLOW.md row `F69` identifies the entry contract and preceding owners. Required predecessors: 27, F68. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `tests/acceptance/test_f69.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `F69`: Do not claim video exists until recorded; use synthetic data; show failure handling and reset; verify links before sending recruiters. Assert create 3-minute and 8-minute scripts covering happy path,missing serial,incompatibility,stock split and human review.

`python tools/run_checks.py --prompt F69` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for demo walkthrough using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `F69`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-f69` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(docs): F69 demo walkthrough`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
