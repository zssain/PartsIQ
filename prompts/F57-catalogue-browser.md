# F57 - Catalogue browser
PHASE: gateway   DEPENDS ON: 02, 06, 18, F59   RISK: high

## GOAL
Read published catalogue with model/category/text filters; page results; show part detail and supersession; staff can inspect fitment and sources. No unpublished import rows exposed; missing number returns 404; literal query cannot become SQL.

## READ FIRST
- AGENTS.md
- docs/HANDOVER.md
- docs/CONSTRAINTS.md
- docs/ARCHITECTURE.md sections 2 and 4
- docs/TECH_SPEC.md
- docs/CONTRACTS.md
- docs/FLOW.md
- spec/file-ownership.json
- features/F57-catalogue-browser.md

## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
No new package. Use the existing exact pins and committed locks; do not install a second library for this feature.

## FILES TO CREATE
- `services/gateway/tests/features/test_f57.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `services/gateway/app/features/f57_catalogue_browser.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/components/features/CatalogueBrowser.tsx`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/lib/features/f57_catalogue_browser.ts`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.

Typed entry contracts:

async def browse_catalogue(actor: ActorContext, request: F57Request) -> F57Result

`F57Request`: query: str | None = None; model_id: int | None = None; category: str | None = None; cursor: str | None = None; limit: int = 20.

`F57Result`: parts: list[PartView]; next_cursor: str | None; version_id: UUID.

Endpoint: `GET /v1/catalogue/parts`. For a public route whose owner is worker/catalogue, gateway validates role and records a durable job/event; it never executes the job inline. Internal routes use the internal token and propagated actor context.

`export function CatalogueBrowser(props: {value: F57Result | null; loading: boolean; error: ApiError | null; onAction: (request: F57Request) => Promise<void>}): React.JSX.Element`. Display loading,empty,error and success states; submit only typed identifiers,never browser-authored compatibility facts.

Implementation sequence:
1. Read published catalogue with model/category/text filters; page results; show part detail and supersession; staff can inspect fitment and sources.
2. No unpublished import rows exposed; missing number returns 404; literal query cannot become SQL.

Required feature behaviours:
- F57 Catalogue browser: Read published catalogue with model/category/text filters; page results; show part detail and supersession; staff can inspect fitment and sources. Failure cases: No unpublished import rows exposed; missing number returns 404; literal query cannot become SQL.

## FILES TO MODIFY
- `apps/web/app/page.tsx`: connect the new implementation through the existing owner; preserve callers and add regression coverage.
- `services/gateway/app/api_v1.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.

Create apps/web/app/staff/catalogue/page.tsx and route to CatalogueBrowser. Add GET /v1/catalogue/parts/{id} through existing search part_detail; do not return import staging rows.

## HOW IT CONNECTS
Owner: gateway; ARCHITECTURE.md section2. FLOW.md row `F57` identifies the entry contract and preceding owners. Required predecessors: 02, 06, 18, F59. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `services/gateway/tests/features/test_f57.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `F57`: No unpublished import rows exposed; missing number returns 404; literal query cannot become SQL. Assert read published catalogue with model/category/text filters.

`python tools/run_checks.py --prompt F57` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for catalogue browser using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `F57`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-f57` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(gateway): F57 catalogue browser`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
