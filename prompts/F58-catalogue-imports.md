# F58 - Catalogue imports
PHASE: worker   DEPENDS ON: 02, 05, 15, F59, F57   RISK: high

## GOAL
Read CSV UTF-8 or XLSX without evaluating formulas; validate row schema,references,serial overlap,supersession cycles and source evidence; show dry-run report; explicit admin publish. Invalid batch changes no published data; file with macros/formulas rejected; 50000-row and 10MiB limits enforced; public demo cannot publish.

## READ FIRST
- AGENTS.md
- docs/HANDOVER.md
- docs/CONSTRAINTS.md
- docs/ARCHITECTURE.md sections 2 and 4
- docs/TECH_SPEC.md
- docs/CONTRACTS.md
- docs/FLOW.md
- spec/file-ownership.json
- features/F58-catalogue-imports.md

## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
- `uv pip install openpyxl==3.1.5` in the task-specific development environment. Add the identical pins to the owning workspace project; synchronize from the shared workspace lock for application execution.

Release dates and registry receipts are in spec/dependency-receipts.json. Use spec/python-requirements.lock and spec/pnpm-lock.yaml as resolution references; do not claim installing these packages proves application compatibility.

## FILES TO CREATE
- `services/worker/tests/features/test_f58.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `services/worker/app/features/f58_catalogue_imports.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/components/features/ImportWizard.tsx`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/lib/features/f58_catalogue_imports.ts`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.

Typed entry contracts:

async def validate_import(actor: ActorContext, request: F58Request) -> F58Result

`F58Request`: batch_id: UUID; lease: JobLease.

`F58Result`: valid: bool; row_count: int; errors: list[ImportErrorView].

Endpoint: `POST /v1/staff/imports`. For a public route whose owner is worker/catalogue, gateway validates role and records a durable job/event; it never executes the job inline. Internal routes use the internal token and propagated actor context.

`export function ImportWizard(props: {value: F58Result | null; loading: boolean; error: ApiError | null; onAction: (request: F58Request) => Promise<void>}): React.JSX.Element`. Display loading,empty,error and success states; submit only typed identifiers,never browser-authored compatibility facts.

Implementation sequence:
1. Read CSV UTF-8 or XLSX without evaluating formulas; validate row schema,references,serial overlap,supersession cycles and source evidence; show dry-run report; explicit admin publish.
2. Invalid batch changes no published data; file with macros/formulas rejected; 50000-row and 10MiB limits enforced; public demo cannot publish.

Required feature behaviours:
- F58 Catalogue imports: Read CSV UTF-8 or XLSX without evaluating formulas; validate row schema,references,serial overlap,supersession cycles and source evidence; show dry-run report; explicit admin publish. Failure cases: Invalid batch changes no published data; file with macros/formulas rejected; 50000-row and 10MiB limits enforced; public demo cannot publish.

## FILES TO MODIFY
- `apps/web/app/page.tsx`: connect the new implementation through the existing owner; preserve callers and add regression coverage.
- `services/worker/app/dispatcher.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.

Gateway adapter must add POST /v1/staff/imports to create import_batches,GET /v1/staff/imports/{id} for validation report,and POST /v1/staff/imports/{id}/validate to enqueue through worker internal control. Public demo can inspect supplied sample validation reports but cannot alter shared catalogue. Explicit admin publication calls F59 only after valid status. Create services/gateway/app/features/f58_import_routes.py as the adapter; register in api_v1.py.

- `services/gateway/app/api_v1.py`: register this prompt's route or handler.

## HOW IT CONNECTS
Owner: worker; ARCHITECTURE.md section2. FLOW.md row `F58` identifies the entry contract and preceding owners. Required predecessors: 02, 05, 15, F59, F57. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `services/worker/tests/features/test_f58.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `F58`: Invalid batch changes no published data; file with macros/formulas rejected; 50000-row and 10MiB limits enforced; public demo cannot publish. Assert read csv utf-8 or xlsx without evaluating formulas.

`python tools/run_checks.py --prompt F58` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for catalogue imports using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `F58`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-f58` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(worker): F58 catalogue imports`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
