# 03 - Workflow schema and database permissions
PHASE: Database   DEPENDS ON: 02   RISK: high

## GOAL
Copy application and RLS SQL from spec/sql. Migrate candidate keys to per-item/per-revision without losing historical rows. Do not backfill invented customer identities; legacy ownerless rows remain inaccessible through customer routes. Create restricted LOGIN credentials administratively and grant each one its service group. Run LangGraph saver setup with MIGRATION_DATABASE_URL into schema checkpoints, snapshot library-created schema, then remove runtime DDL privileges. Test two actors on a reused connection pool.

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
- features/F12-conversation-memory.md
- features/F49-audit-trail.md

## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
No new package. Use the existing exact pins and committed locks; do not install a second library for this feature.

## FILES TO CREATE
- `supabase/migrations/20261011000300_application.sql`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `supabase/migrations/20261011000400_rls.sql`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tools/checkpoints_setup.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tools/schema_receipt.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tests/integration/conftest.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tests/foundations/test_03.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.

Typed entry contracts:

async def setup_checkpoints(dsn: str) -> None; async def collect_schema_receipt(dsn: str) -> SchemaReceipt; no application service invokes setup_checkpoints.

Implementation sequence:
1. Copy application and RLS SQL from spec/sql.
2. Migrate candidate keys to per-item/per-revision without losing historical rows.
3. Do not backfill invented customer identities; legacy ownerless rows remain inaccessible through customer routes.
4. Create restricted LOGIN credentials administratively and grant each one its service group.
5. Run LangGraph saver setup with MIGRATION_DATABASE_URL into schema checkpoints, snapshot library-created schema, then remove runtime DDL privileges.
6. Test two actors on a reused connection pool.

Required feature behaviours:
- F04 Demo isolation: Bind each session to verified anonymous Supabase identity; check generation and expiry on every read, write and worker completion; exclude demos from operational metrics by default. Failure cases: Expired, reset and foreign sessions fail; missing identity context returns no rows.
- F12 Conversation memory: Persist all messages and typed current state; compact context using retained structured facts; resume by enquiry/revision; never mix customer sessions. Failure cases: Restart retains unresolved questions; old revision events are ignored and audited; foreign thread ID denied.
- F49 Audit trail: Append actor,request,entity,revision and minimal before/after metadata for AI suggestions and human changes; redact secrets and full sensitive payloads. Failure cases: Application UPDATE,DELETE,TRUNCATE fail; audit write failure rolls back approval; database-owner powers documented honestly.

## FILES TO MODIFY
No existing runtime file requires modification beyond the documentation updates and package manifests named here.

## HOW IT CONNECTS
Owner: Database; ARCHITECTURE.md section2. FLOW.md row `03` identifies the entry contract and preceding owners. Required predecessors: 02. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `tests/foundations/test_03.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `F04`: Expired, reset and foreign sessions fail; missing identity context returns no rows. Assert bind each session to verified anonymous supabase identity.
- `F12`: Restart retains unresolved questions; old revision events are ignored and audited; foreign thread ID denied. Assert persist all messages and typed current state.
- `F49`: Application UPDATE,DELETE,TRUNCATE fail; audit write failure rolls back approval; database-owner powers documented honestly. Assert append actor,request,entity,revision and minimal before/after metadata for ai suggestions and human changes.

`python tools/run_checks.py --prompt 03` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for workflow schema and database permissions using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `03`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-03` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(database): 03 workflow schema and database permissions`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
