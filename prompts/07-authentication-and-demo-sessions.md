# 07 - Authentication and demo sessions
PHASE: Gateway   DEPENDS ON: 06   RISK: high

## GOAL
Verify Supabase JWT issuer,audience,expiry and allowed algorithm through cached JWKS; refresh on unknown kid once. Fetch staff membership from DB, never JWT user_metadata. Use Supabase anonymous sign-in for public demos. Session creation requires that authenticated anonymous identity; rate limit before database work. Reset under row lock with idempotency key and generation increment. Reviewer access is assigned-only for real enquiries; admin may manage assignments. Demo review capability applies only to own active session.

## READ FIRST
- AGENTS.md
- docs/HANDOVER.md
- docs/CONSTRAINTS.md
- docs/ARCHITECTURE.md sections 2 and 4
- docs/TECH_SPEC.md
- docs/CONTRACTS.md
- docs/FLOW.md
- spec/file-ownership.json
- features/F03-demo-role-switching.md
- features/F04-demo-isolation.md
- features/F05-demo-reset.md
- features/F54-access-and-permissions.md

## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
No new package. Use the existing exact pins and committed locks; do not install a second library for this feature.

## FILES TO CREATE
- `services/gateway/app/auth.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/gateway/app/permissions.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/gateway/app/demo.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tests/foundations/test_07.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.

Typed entry contracts:

async def authenticate(token: str) -> ActorContext; async def require_access(actor: ActorContext, enquiry_id: UUID, action: AccessAction) -> None; async def create_demo(actor: ActorContext) -> DemoSession; async def reset_demo(actor: ActorContext, key: UUID) -> DemoSession.

Implementation sequence:
1. Verify Supabase JWT issuer,audience,expiry and allowed algorithm through cached JWKS; refresh on unknown kid once.
2. Fetch staff membership from DB, never JWT user_metadata.
3. Use Supabase anonymous sign-in for public demos.
4. Session creation requires that authenticated anonymous identity; rate limit before database work.
5. Reset under row lock with idempotency key and generation increment.
6. Reviewer access is assigned-only for real enquiries; admin may manage assignments.
7. Demo review capability applies only to own active session.

Required feature behaviours:
- F03 Demo role switching: Switch the presentation between customer and reviewer using the same anonymous identity and session; authorize review only for enquiries belonging to that active session. Failure cases: Forged reviewer role never grants staff membership; another visitor's enquiry returns 404.
- F04 Demo isolation: Bind each session to verified anonymous Supabase identity; check generation and expiry on every read, write and worker completion; exclude demos from operational metrics by default. Failure cases: Expired, reset and foreign sessions fail; missing identity context returns no rows.
- F05 Demo reset: Lock session; increment generation; cancel unfinished jobs from prior generation; enqueue Storage cleanup; keep minimal audit; create fresh scenario enquiries on explicit selection. Failure cases: Late OCR from old generation cannot update current data; repeated reset idempotency key returns the same generation.
- F54 Access and permissions: Verify Supabase issuer,audience,signature,expiry; derive identity server-side; enforce assigned-only review; keep credentials server-side; disable public real-client signup. Failure cases: Forged role claim ignored; missing context denies rows; preview cannot reach prod database; demo cannot publish shared catalogue.

## FILES TO MODIFY
- `services/gateway/app/main.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.
- `services/gateway/app/routes.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.
- `services/gateway/app/security.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.

## HOW IT CONNECTS
Owner: Gateway; ARCHITECTURE.md section2. FLOW.md row `07` identifies the entry contract and preceding owners. Required predecessors: 06. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `tests/foundations/test_07.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `F03`: Forged reviewer role never grants staff membership; another visitor's enquiry returns 404. Assert switch the presentation between customer and reviewer using the same anonymous identity and session.
- `F04`: Expired, reset and foreign sessions fail; missing identity context returns no rows. Assert bind each session to verified anonymous supabase identity.
- `F05`: Late OCR from old generation cannot update current data; repeated reset idempotency key returns the same generation. Assert lock session.
- `F54`: Forged role claim ignored; missing context denies rows; preview cannot reach prod database; demo cannot publish shared catalogue. Assert verify supabase issuer,audience,signature,expiry.

`python tools/run_checks.py --prompt 07` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for authentication and demo sessions using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `07`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-07` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(gateway): 07 authentication and demo sessions`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
