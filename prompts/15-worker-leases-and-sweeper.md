# 15 - Worker leases and sweeper
PHASE: Worker   DEPENDS ON: 14   RISK: high

## GOAL
Persist jobs before Redis push; sweeper scans available pending jobs and running jobs with expired leases. Claim FOR UPDATE SKIP LOCKED with fresh token and increment attempts. Heartbeat at10seconds with45second lease; use bounded concurrency one OCR and one PDF initially. Complete transaction requires matching token,current enquiry revision and session generation. Worker writes workflow_events for OCR completion,never calls orchestrator HTTP. Expose authenticated internal signing route only on Docker network. Graceful shutdown stops claiming and allows current lease completion.

## READ FIRST
- AGENTS.md
- docs/HANDOVER.md
- docs/CONSTRAINTS.md
- docs/ARCHITECTURE.md sections 2 and 4
- docs/TECH_SPEC.md
- docs/CONTRACTS.md
- docs/FLOW.md
- spec/file-ownership.json
- features/F05-demo-reset.md
- features/F14-nameplate-ocr.md
- features/F51-background-jobs.md
- features/F52-retry-and-deduplication.md

## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
No new package. Use the existing exact pins and committed locks; do not install a second library for this feature.

## FILES TO CREATE
- `services/worker/app/main.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/worker/app/dispatcher.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/worker/app/leases.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/worker/app/sweeper.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/worker/app/internal.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/worker/tests/features/test_f51.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `services/worker/tests/features/test_f52.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `tests/foundations/test_15.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.

Typed entry contracts:

async def claim_job(job_id: UUID, worker_id: str) -> JobLease | None; async def heartbeat(lease: JobLease) -> bool; async def finish_job(lease: JobLease, result: JobResult) -> bool; async def sweep_once(now: datetime) -> int.

Implementation sequence:
1. Persist jobs before Redis push; sweeper scans available pending jobs and running jobs with expired leases.
2. Claim FOR UPDATE SKIP LOCKED with fresh token and increment attempts.
3. Heartbeat at10seconds with45second lease; use bounded concurrency one OCR and one PDF initially.
4. Complete transaction requires matching token,current enquiry revision and session generation.
5. Worker writes workflow_events for OCR completion,never calls orchestrator HTTP.
6. Expose authenticated internal signing route only on Docker network.
7. Graceful shutdown stops claiming and allows current lease completion.

Required feature behaviours:
- F05 Demo reset: Lock session; increment generation; cancel unfinished jobs from prior generation; enqueue Storage cleanup; keep minimal audit; create fresh scenario enquiries on explicit selection. Failure cases: Late OCR from old generation cannot update current data; repeated reset idempotency key returns the same generation.
- F14 Nameplate OCR: Read validated nameplate via OpenAI vision; return model_text,serial_text,issues and source attachment; persist result only with current lease and revision. Failure cases: Unreadable fields remain null; vision instructions in photo are untrusted; timeout is bounded and creates recoverable status.
- F51 Background jobs: Persist job before Redis dispatch; dispatcher claims by ID; sweeper redispatches pending/expired jobs; worker handles OCR,PDF,imports and cleanup. Failure cases: Redis loss does not lose DB job; unavailable Redis rate limiter fails closed; heavy work never blocks HTTP intake.
- F52 Retry and deduplication: Claim with FOR UPDATE SKIP LOCKED; assign lease token; heartbeat; retry transient errors with backoff up to max attempts; fence final writes by lease token. Failure cases: Expired worker cannot commit; permanent validation failure not retried; provider timeout marked uncertain and budget held conservatively.

## FILES TO MODIFY
No existing runtime file requires modification beyond the documentation updates and package manifests named here.

## HOW IT CONNECTS
Owner: Worker; ARCHITECTURE.md section2. FLOW.md row `15` identifies the entry contract and preceding owners. Required predecessors: 14. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `services/worker/tests/features/test_f51.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `services/worker/tests/features/test_f52.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `tests/foundations/test_15.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `F05`: Late OCR from old generation cannot update current data; repeated reset idempotency key returns the same generation. Assert lock session.
- `F14`: Unreadable fields remain null; vision instructions in photo are untrusted; timeout is bounded and creates recoverable status. Assert read validated nameplate via openai vision.
- `F51`: Redis loss does not lose DB job; unavailable Redis rate limiter fails closed; heavy work never blocks HTTP intake. Assert persist job before redis dispatch.
- `F52`: Expired worker cannot commit; permanent validation failure not retried; provider timeout marked uncertain and budget held conservatively. Assert claim with for update skip locked.

`python tools/run_checks.py --prompt 15` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for worker leases and sweeper using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `15`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-15` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(worker): 15 worker leases and sweeper`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
