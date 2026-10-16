# 14 - Approval and revision transactions
PHASE: Orchestrator   DEPENDS ON: 13   RISK: high

## GOAL
Lock enquiry; re-read actor permission via assigned reviewer or own demo capability; compare expected revision and current catalogue; refresh stock through search; reject changed plan. Reverify edited prose and facts. Insert approved decision,approved parts,one recommendation message and audit in one DB transaction. Rejection records reason but does not publish recommendation. Corrections increment revision and append immutable snapshot; no update to historical approval. Idempotency key binds request hash.

## READ FIRST
- AGENTS.md
- docs/HANDOVER.md
- docs/CONSTRAINTS.md
- docs/ARCHITECTURE.md sections 2 and 4
- docs/TECH_SPEC.md
- docs/CONTRACTS.md
- docs/FLOW.md
- spec/file-ownership.json
- features/F39-review-actions.md
- features/F40-approval-invalidation.md
- features/F47-human-publication-gate.md
- features/F49-audit-trail.md

## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
No new package. Use the existing exact pins and committed locks; do not install a second library for this feature.

## FILES TO CREATE
- `services/orchestrator/app/approval.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/orchestrator/app/revisions.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/orchestrator/tests/features/test_f40.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `services/orchestrator/tests/features/test_f47.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `tests/acceptance/test_f49.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `tests/foundations/test_14.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.

Typed entry contracts:

async def approve(actor: ActorContext, request: ApprovalRequest, key: UUID) -> ApprovalResult; async def reject(actor: ActorContext, request: RejectionRequest, key: UUID) -> ReviewResult; async def revise(actor: ActorContext, request: RevisionRequest) -> EnquiryView.

Implementation sequence:
1. Lock enquiry; re-read actor permission via assigned reviewer or own demo capability; compare expected revision and current catalogue; refresh stock through search; reject changed plan.
2. Reverify edited prose and facts.
3. Insert approved decision,approved parts,one recommendation message and audit in one DB transaction.
4. Rejection records reason but does not publish recommendation.
5. Corrections increment revision and append immutable snapshot; no update to historical approval.
6. Idempotency key binds request hash.

Required feature behaviours:
- F39 Review actions: Approve only verified current draft; edit prose through controlled schema then reverify; reject with reason; record actor and idempotency key. Failure cases: Double-click publishes once; concurrent edit defeats stale approval; failed verification blocks publication.
- F40 Approval invalidation: Bind approval to revision and verified fact hash; any identity,quantity,selection or catalogue-sensitive change requires new draft and approval. Failure cases: Old approval cannot authorize new revision; late workflow update cannot overwrite approved current state.
- F47 Human publication gate: Only approval service inserts recommendation messages; lock enquiry and recheck role,revision and verification; unique publication index prevents duplicates. Failure cases: No worker/specialist write tool can publish; database rejects recommendation lacking matching approved decision.
- F49 Audit trail: Append actor,request,entity,revision and minimal before/after metadata for AI suggestions and human changes; redact secrets and full sensitive payloads. Failure cases: Application UPDATE,DELETE,TRUNCATE fail; audit write failure rolls back approval; database-owner powers documented honestly.

## FILES TO MODIFY
- `services/orchestrator/app/graph.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.
- `services/orchestrator/app/handlers.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.

## HOW IT CONNECTS
Owner: Orchestrator; ARCHITECTURE.md section2. FLOW.md row `14` identifies the entry contract and preceding owners. Required predecessors: 13. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `services/orchestrator/tests/features/test_f40.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `services/orchestrator/tests/features/test_f47.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `tests/acceptance/test_f49.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `tests/foundations/test_14.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `F39`: Double-click publishes once; concurrent edit defeats stale approval; failed verification blocks publication. Assert approve only verified current draft.
- `F40`: Old approval cannot authorize new revision; late workflow update cannot overwrite approved current state. Assert bind approval to revision and verified fact hash.
- `F47`: No worker/specialist write tool can publish; database rejects recommendation lacking matching approved decision. Assert only approval service inserts recommendation messages.
- `F49`: Application UPDATE,DELETE,TRUNCATE fail; audit write failure rolls back approval; database-owner powers documented honestly. Assert append actor,request,entity,revision and minimal before/after metadata for ai suggestions and human changes.

`python tools/run_checks.py --prompt 14` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for approval and revision transactions using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `14`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-14` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(orchestrator): 14 approval and revision transactions`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
