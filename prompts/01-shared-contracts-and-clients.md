# 01 - Shared contracts and clients
PHASE: Common   DEPENDS ON: 00   RISK: high

## GOAL
Implement the exact contract models from spec/contracts.py. Preserve text.py and DB pool behaviour. Wrap every OpenAI invocation with explicit timeout, output token limit and budget reservation; never retry inside both SDK and wrapper. Set SDK max_retries=0 and wrapper max attempts=2. Log safe error code and request ID. Insert audit within caller transaction for business writes; fail approval if audit fails. Set app.actor_id using set_config with is_local=true inside the transaction and clear no session-global state.

## READ FIRST
- AGENTS.md
- docs/HANDOVER.md
- docs/CONSTRAINTS.md
- docs/ARCHITECTURE.md sections 2 and 4
- docs/TECH_SPEC.md
- docs/CONTRACTS.md
- docs/FLOW.md
- spec/file-ownership.json
- features/F49-audit-trail.md
- features/F64-latency-and-ai-cost.md
- features/F67-traces.md

## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
- `uv pip install fastapi==0.135.1 uvicorn==0.41.0 pydantic==2.12.5 pydantic-settings==2.13.1 httpx==0.28.1 asyncpg==0.31.0 psycopg[binary]==3.3.3 psycopg-pool==3.3.0 redis==7.3.0 openai==3.19.2 structlog==25.5.0 tenacity==9.1.2 PyJWT==2.12.1 cryptography==46.0.5 python-multipart==0.0.22` in the task-specific development environment. Add the identical pins to the owning workspace project; synchronize from the shared workspace lock for application execution.

Release dates and registry receipts are in spec/dependency-receipts.json. Use spec/python-requirements.lock and spec/pnpm-lock.yaml as resolution references; do not claim installing these packages proves application compatibility.

## FILES TO CREATE
- `libs/partsiq_common/partsiq_common/contracts.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `libs/partsiq_common/partsiq_common/audit.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `libs/partsiq_common/partsiq_common/errors.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `libs/partsiq_common/partsiq_common/ai/client.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `libs/partsiq_common/partsiq_common/ai/budget.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `libs/partsiq_common/partsiq_common/telemetry.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `libs/partsiq_common/partsiq_common/security_context.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `libs/partsiq_common/partsiq_common/ai/prices.json`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tests/foundations/test_01.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.

Typed entry contracts:

async def call_structured(request: AIRequest, budget: BudgetReservation) -> AIResult; async def append_audit(conn: AsyncConnection, event: AuditEvent) -> int; async def actor_transaction(actor: ActorContext) -> AsyncIterator[AsyncConnection].

Implementation sequence:
1. Implement the exact contract models from spec/contracts.py.
2. Preserve text.py and DB pool behaviour.
3. Wrap every OpenAI invocation with explicit timeout, output token limit and budget reservation; never retry inside both SDK and wrapper.
4. Set SDK max_retries=0 and wrapper max attempts=2.
5. Log safe error code and request ID.
6. Insert audit within caller transaction for business writes; fail approval if audit fails.
7. Set app.actor_id using set_config with is_local=true inside the transaction and clear no session-global state.

Required feature behaviours:
- F49 Audit trail: Append actor,request,entity,revision and minimal before/after metadata for AI suggestions and human changes; redact secrets and full sensitive payloads. Failure cases: Application UPDATE,DELETE,TRUNCATE fail; audit write failure rolls back approval; database-owner powers documented honestly.
- F64 Latency and AI cost: Measure stages with monotonic clock; log model/token usage and estimated cost; reserve confirmed free credit before each attempt; expose consumed/reserved allowance. Failure cases: Unknown price or expired credit blocks calls; concurrent reservations cannot exceed cap; API key validity never implies free credit.
- F67 Traces: Propagate request/enquiry/job IDs; capture stage timing and safe status; export optional Langfuse traces with payload redaction; operate normally when tracing unavailable. Failure cases: No raw key or full photo logged; exporter outage never breaks approval; budget accounting remains local and authoritative.

Exact package markers and bundled assets created by this step:
- `libs/partsiq_common/partsiq_common/ai/__init__.py`

## FILES TO MODIFY
No existing runtime file requires modification beyond the documentation updates and package manifests named here.

## HOW IT CONNECTS
Owner: Common; ARCHITECTURE.md section2. FLOW.md row `01` identifies the entry contract and preceding owners. Required predecessors: 00. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `tests/foundations/test_01.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `F49`: Application UPDATE,DELETE,TRUNCATE fail; audit write failure rolls back approval; database-owner powers documented honestly. Assert append actor,request,entity,revision and minimal before/after metadata for ai suggestions and human changes.
- `F64`: Unknown price or expired credit blocks calls; concurrent reservations cannot exceed cap; API key validity never implies free credit. Assert measure stages with monotonic clock.
- `F67`: No raw key or full photo logged; exporter outage never breaks approval; budget accounting remains local and authoritative. Assert propagate request/enquiry/job ids.

`python tools/run_checks.py --prompt 01` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for shared contracts and clients using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `01`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-01` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(common): 01 shared contracts and clients`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
