# 22 - Security and failure recovery gate
PHASE: Quality   DEPENDS ON: F65   RISK: high

## GOAL
Run against disposable local Supabase including auth and storage. Exercise foreign sessions,assigned-only reviewer,reset races,expired JWT,upload bombs,prompt injection,Redis down,worker crash,stale lease,API timeout and simultaneous approvals. Assert no secret in browser bundle or logs. Block tests when DB hostname/project matches production. Retain actual command output and failed cases; never mark blocked tests passed.

## READ FIRST
- AGENTS.md
- docs/HANDOVER.md
- docs/CONSTRAINTS.md
- docs/ARCHITECTURE.md sections 2 and 4
- docs/TECH_SPEC.md
- docs/CONTRACTS.md
- docs/FLOW.md
- spec/file-ownership.json
- features/F04-demo-isolation.md
- features/F53-graceful-failures.md
- features/F54-access-and-permissions.md

## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
No new package. Use the existing exact pins and committed locks; do not install a second library for this feature.

## FILES TO CREATE
- `tests/integration/test_security_recovery.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tests/integration/test_rls.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tests/integration/test_budget_races.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tests/e2e/security.spec.ts`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/gateway/tests/features/test_f04.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `apps/web/tests/features/f53.test.tsx`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `services/gateway/tests/features/test_f54.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `tests/foundations/test_22.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.

Typed entry contracts:

def assert_disposable_environment(config: TestConfig) -> None; test suites instantiate existing service entry points without new business logic.

Implementation sequence:
1. Run against disposable local Supabase including auth and storage.
2. Exercise foreign sessions,assigned-only reviewer,reset races,expired JWT,upload bombs,prompt injection,Redis down,worker crash,stale lease,API timeout and simultaneous approvals.
3. Assert no secret in browser bundle or logs.
4. Block tests when DB hostname/project matches production.
5. Retain actual command output and failed cases; never mark blocked tests passed.

Required feature behaviours:
- F04 Demo isolation: Bind each session to verified anonymous Supabase identity; check generation and expiry on every read, write and worker completion; exclude demos from operational metrics by default. Failure cases: Expired, reset and foreign sessions fail; missing identity context returns no rows.
- F53 Graceful failures: Map stable error codes to bilingual recovery guidance; distinguish validation,quota,service outage and staff-required states; preserve user input. Failure cases: No raw stack traces or keys; retry only safe idempotent action; search lexical fallback clearly reported.
- F54 Access and permissions: Verify Supabase issuer,audience,signature,expiry; derive identity server-side; enforce assigned-only review; keep credentials server-side; disable public real-client signup. Failure cases: Forged role claim ignored; missing context denies rows; preview cannot reach prod database; demo cannot publish shared catalogue.

## FILES TO MODIFY
No existing runtime file requires modification beyond the documentation updates and package manifests named here.

## HOW IT CONNECTS
Owner: Quality; ARCHITECTURE.md section2. FLOW.md row `22` identifies the entry contract and preceding owners. Required predecessors: F65. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `services/gateway/tests/features/test_f04.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `apps/web/tests/features/f53.test.tsx`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `services/gateway/tests/features/test_f54.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `tests/foundations/test_22.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `F04`: Expired, reset and foreign sessions fail; missing identity context returns no rows. Assert bind each session to verified anonymous supabase identity.
- `F53`: No raw stack traces or keys; retry only safe idempotent action; search lexical fallback clearly reported. Assert map stable error codes to bilingual recovery guidance.
- `F54`: Forged role claim ignored; missing context denies rows; preview cannot reach prod database; demo cannot publish shared catalogue. Assert verify supabase issuer,audience,signature,expiry.

`python tools/run_checks.py --prompt 22` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for security and failure recovery gate using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `22`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-22` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(quality): 22 security and failure recovery gate`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
