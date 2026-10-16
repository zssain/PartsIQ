# F68 - Recruiter documentation
PHASE: docs   DEPENDS ON: 21, 23, 22, 24, 25, 26, 27   RISK: high

## GOAL
Write concise overview,real architecture,quick start,demo paths,tests,trade-offs and limitations; link measured evidence; explain deterministic decisions and specialist tools. No invented accuracy,uptime,client relationship or production adoption; distinguish implementation status from specification.

## READ FIRST
- AGENTS.md
- docs/HANDOVER.md
- docs/CONSTRAINTS.md
- docs/ARCHITECTURE.md sections 2 and 4
- docs/TECH_SPEC.md
- docs/CONTRACTS.md
- docs/FLOW.md
- spec/file-ownership.json
- features/F68-recruiter-documentation.md

## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
- `uv pip install python-docx==1.2.0` in the task-specific development environment. Add the identical pins to the owning workspace project; synchronize from the shared workspace lock for application execution.

Release dates and registry receipts are in spec/dependency-receipts.json. Use spec/python-requirements.lock and spec/pnpm-lock.yaml as resolution references; do not claim installing these packages proves application compatibility.

## FILES TO CREATE
- `tests/acceptance/test_f68.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `docs/RECRUITER_GUIDE.md`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.

Typed entry contracts:

Documentation contract: README.md and docs/RECRUITER_GUIDE.md

`F68Request`: source: validated hosted and test receipts.

`F68Result`: README.md and docs/RECRUITER_GUIDE.md.

Endpoint: `none`. For a public route whose owner is worker/catalogue, gateway validates role and records a durable job/event; it never executes the job inline. Internal routes use the internal token and propagated actor context.

Implementation sequence:
1. Write concise overview,real architecture,quick start,demo paths,tests,trade-offs and limitations; link measured evidence; explain deterministic decisions and specialist tools.
2. No invented accuracy,uptime,client relationship or production adoption; distinguish implementation status from specification.

Required feature behaviours:
- F68 Recruiter documentation: Write concise overview,real architecture,quick start,demo paths,tests,trade-offs and limitations; link measured evidence; explain deterministic decisions and specialist tools. Failure cases: No invented accuracy,uptime,client relationship or production adoption; distinguish implementation status from specification.

## FILES TO MODIFY
- `README.md`: connect the new implementation through the existing owner; preserve callers and add regression coverage.

## HOW IT CONNECTS
Owner: docs; ARCHITECTURE.md section2. FLOW.md row `F68` identifies the entry contract and preceding owners. Required predecessors: 21, 23, 22, 24, 25, 26, 27. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `tests/acceptance/test_f68.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `F68`: No invented accuracy,uptime,client relationship or production adoption; distinguish implementation status from specification. Assert write concise overview,real architecture,quick start,demo paths,tests,trade-offs and limitations.

`python tools/run_checks.py --prompt F68` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for recruiter documentation using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `F68`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-f68` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(docs): F68 recruiter documentation`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
