# 23 - Observability and credit limits
PHASE: Operations   DEPENDS ON: 21   RISK: high

## GOAL
Use common telemetry and AI wrapper from01; add optional Langfuse export with redacted payload and strict timeouts. Record latency,cost,token and stage outcomes locally. Allowance is manually confirmed free credit,not inferred from key. Require amount,expiry and acknowledged no-paid-fallback; default disabled. Reserve worst-case token/image usage atomically for each attempt; uncertain requests retain reservation. Throttle per session and daily quota. Trace exporter failure cannot bypass local accounting.

## READ FIRST
- AGENTS.md
- docs/HANDOVER.md
- docs/CONSTRAINTS.md
- docs/ARCHITECTURE.md sections 2 and 4
- docs/TECH_SPEC.md
- docs/CONTRACTS.md
- docs/FLOW.md
- spec/file-ownership.json
- features/F64-latency-and-ai-cost.md
- features/F67-traces.md

## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
- `uv pip install langfuse==3.14.5` in the task-specific development environment. Add the identical pins to the owning workspace project; synchronize from the shared workspace lock for application execution.

Release dates and registry receipts are in spec/dependency-receipts.json. Use spec/python-requirements.lock and spec/pnpm-lock.yaml as resolution references; do not claim installing these packages proves application compatibility.

## FILES TO CREATE
- `services/gateway/app/metrics.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tools/credit_allowance.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tools/check_readiness.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tests/acceptance/test_f64.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `tests/acceptance/test_f67.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `tests/foundations/test_23.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.

Typed entry contracts:

async def get_metrics(actor: ActorContext, query: MetricsQuery) -> MetricsView; def validate_allowance(amount: Decimal, expires_at: datetime, paid_budget: Decimal) -> CreditAllowance; async def readiness_report() -> ReadinessReport.

Implementation sequence:
1. Use common telemetry and AI wrapper from01; add optional Langfuse export with redacted payload and strict timeouts.
2. Record latency,cost,token and stage outcomes locally.
3. Allowance is manually confirmed free credit,not inferred from key.
4. Require amount,expiry and acknowledged no-paid-fallback; default disabled.
5. Reserve worst-case token/image usage atomically for each attempt; uncertain requests retain reservation.
6. Throttle per session and daily quota.
7. Trace exporter failure cannot bypass local accounting.

Required feature behaviours:
- F64 Latency and AI cost: Measure stages with monotonic clock; log model/token usage and estimated cost; reserve confirmed free credit before each attempt; expose consumed/reserved allowance. Failure cases: Unknown price or expired credit blocks calls; concurrent reservations cannot exceed cap; API key validity never implies free credit.
- F67 Traces: Propagate request/enquiry/job IDs; capture stage timing and safe status; export optional Langfuse traces with payload redaction; operate normally when tracing unavailable. Failure cases: No raw key or full photo logged; exporter outage never breaks approval; budget accounting remains local and authoritative.

## FILES TO MODIFY
- `libs/partsiq_common/partsiq_common/ai/budget.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.
- `libs/partsiq_common/partsiq_common/ai/client.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.
- `libs/partsiq_common/partsiq_common/telemetry.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.

## HOW IT CONNECTS
Owner: Operations; ARCHITECTURE.md section2. FLOW.md row `23` identifies the entry contract and preceding owners. Required predecessors: 21. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `tests/acceptance/test_f64.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `tests/acceptance/test_f67.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `tests/foundations/test_23.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `F64`: Unknown price or expired credit blocks calls; concurrent reservations cannot exceed cap; API key validity never implies free credit. Assert measure stages with monotonic clock.
- `F67`: No raw key or full photo logged; exporter outage never breaks approval; budget accounting remains local and authoritative. Assert propagate request/enquiry/job ids.

`python tools/run_checks.py --prompt 23` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for observability and credit limits using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `23`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-23` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(operations): 23 observability and credit limits`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
