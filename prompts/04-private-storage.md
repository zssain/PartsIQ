# 04 - Private storage
PHASE: Gateway/worker   DEPENDS ON: 03   RISK: high

## GOAL
Create four private buckets from exact SQL. Gateway signs owner uploads using verified user token and pending attachment policy. Worker alone holds storage administration credential for export,evidence,import and cleanup operations; never use it as database REST bypass. Gateway first authorizes each read and asks internal worker signing handler with typed object ID, never arbitrary key. Signed links expire after 60 seconds; strip them from logs. Confirm actual bytes before marking validated.

## READ FIRST
- AGENTS.md
- docs/HANDOVER.md
- docs/CONSTRAINTS.md
- docs/ARCHITECTURE.md sections 2 and 4
- docs/TECH_SPEC.md
- docs/CONTRACTS.md
- docs/FLOW.md
- spec/file-ownership.json
- features/F13-private-uploads.md

## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
No new package. Use the existing exact pins and committed locks; do not install a second library for this feature.

## FILES TO CREATE
- `supabase/migrations/20261011000500_storage.sql`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/gateway/app/storage.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/worker/app/storage.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tests/foundations/test_04.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.

Typed entry contracts:

async def create_upload(actor: ActorContext, request: UploadRequest) -> UploadTicket; async def sign_download(request: DownloadRequest) -> DownloadTicket; async def remove_object(bucket: str, object_key: str) -> None.

Implementation sequence:
1. Create four private buckets from exact SQL.
2. Gateway signs owner uploads using verified user token and pending attachment policy.
3. Worker alone holds storage administration credential for export,evidence,import and cleanup operations; never use it as database REST bypass.
4. Gateway first authorizes each read and asks internal worker signing handler with typed object ID, never arbitrary key.
5. Signed links expire after 60 seconds; strip them from logs.
6. Confirm actual bytes before marking validated.

Required feature behaviours:
- F13 Private uploads: Create pending attachment and unique object path; use signed upload; validate actual bytes and magic type after confirmation; strip EXIF and cap decoded pixels before OCR. Failure cases: Wrong MIME, oversized content, image decompression bomb, duplicate confirmation and nonexistent object handled explicitly.

Exact package markers and bundled assets created by this step:
- `services/worker/app/__init__.py`

## FILES TO MODIFY
No existing runtime file requires modification beyond the documentation updates and package manifests named here.

## HOW IT CONNECTS
Owner: Gateway/worker; ARCHITECTURE.md section2. FLOW.md row `04` identifies the entry contract and preceding owners. Required predecessors: 03. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `tests/foundations/test_04.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `F13`: Wrong MIME, oversized content, image decompression bomb, duplicate confirmation and nonexistent object handled explicitly. Assert create pending attachment and unique object path.

`python tools/run_checks.py --prompt 04` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for private storage using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `04`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-04` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(gateway-worker): 04 private storage`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
