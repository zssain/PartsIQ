# 20 - Staff workspace and timeline
PHASE: Web   DEPENDS ON: 19   RISK: high

## GOAL
Render current review snapshot with revision badge,candidates,evidence references,allocation,draft and named verification results. Only current verified state enables approve. Post expected revision and idempotency key; on409 reload and require explicit new review. Edit prose uses structured fields. Reject requires reason. Real reviewers only see assignments; demo review remains ownsession. Add approved PDF action and display queue status.

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
- features/F18-progress-timeline.md
- features/F27-match-explanations.md
- features/F32-warehouse-stock.md
- features/F37-review-workspace.md
- features/F39-review-actions.md
- features/F53-graceful-failures.md
- features/F61-enquiry-pdf.md

## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
No new package. Use the existing exact pins and committed locks; do not install a second library for this feature.

## FILES TO CREATE
- `apps/web/app/staff/inbox/page.tsx`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/app/staff/enquiries/[id]/page.tsx`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/components/review/Workspace.tsx`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/components/review/ApprovalControls.tsx`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/components/review/Timeline.tsx`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/gateway/tests/features/test_f03.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `apps/web/tests/features/f18.test.tsx`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `apps/web/tests/features/f27.test.tsx`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `services/search/tests/features/test_f32.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `apps/web/tests/features/f37.test.tsx`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `services/orchestrator/tests/features/test_f39.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `services/worker/tests/features/test_f61.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `tests/foundations/test_20.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.

Typed entry contracts:

export function Workspace(props: {enquiryId: string}): React.JSX.Element; export function ApprovalControls(props: {review: ReviewView; onChanged: () => Promise<void>}): React.JSX.Element.

Implementation sequence:
1. Render current review snapshot with revision badge,candidates,evidence references,allocation,draft and named verification results.
2. Only current verified state enables approve.
3. Post expected revision and idempotency key; on409 reload and require explicit new review.
4. Edit prose uses structured fields.
5. Reject requires reason.
6. Real reviewers only see assignments; demo review remains ownsession.
7. Add approved PDF action and display queue status.

Required feature behaviours:
- F03 Demo role switching: Switch the presentation between customer and reviewer using the same anonymous identity and session; authorize review only for enquiries belonging to that active session. Failure cases: Forged reviewer role never grants staff membership; another visitor's enquiry returns 404.
- F18 Progress timeline: Show persisted stages, wait reason and last update; poll with bounded backoff; reconnect using server state; separate waiting for customer from waiting for staff. Failure cases: No fake completed progress; failed poll retains last state and offers retry; hidden tabs reduce polling.
- F27 Match explanations: Show actual alias, machine configuration, supersession chain and fitment reference; derive explanations from search evidence rather than invented model prose. Failure cases: Absent evidence shown as unavailable; user HTML is escaped; scores never labelled calibrated probability.
- F32 Warehouse stock: Show available quantity as on_hand minus reserved; include timestamp and warehouse name; keep display and planner using same snapshot. Failure cases: Negative stock blocked; stock unavailable never displayed as zero without explanation; unknown warehouse rejected.
- F37 Review workspace: Assemble current extraction, items, candidates, evidence, stock, draft and timeline; show verification failures; separate staff-only notes from customer messages. Failure cases: Missing panels show explicit empty states; stale revision disables approval; unassigned reviewer receives 404.
- F39 Review actions: Approve only verified current draft; edit prose through controlled schema then reverify; reject with reason; record actor and idempotency key. Failure cases: Double-click publishes once; concurrent edit defeats stale approval; failed verification blocks publication.
- F53 Graceful failures: Map stable error codes to bilingual recovery guidance; distinguish validation,quota,service outage and staff-required states; preserve user input. Failure cases: No raw stack traces or keys; retry only safe idempotent action; search lexical fallback clearly reported.
- F61 Enquiry PDF: Export approved revision only; render logo,bilingual customer text,verified selections,estimates and references; embed Arabic fonts; store private object and signed download. Failure cases: Exclude notes and secrets; stale or unapproved revision rejected; long Arabic names wrap without clipping; no prices or quotation title.

## FILES TO MODIFY
No existing runtime file requires modification beyond the documentation updates and package manifests named here.

## HOW IT CONNECTS
Owner: Web; ARCHITECTURE.md section2. FLOW.md row `20` identifies the entry contract and preceding owners. Required predecessors: 19. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `services/gateway/tests/features/test_f03.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `apps/web/tests/features/f18.test.tsx`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `apps/web/tests/features/f27.test.tsx`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `services/search/tests/features/test_f32.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `apps/web/tests/features/f37.test.tsx`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `services/orchestrator/tests/features/test_f39.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `services/worker/tests/features/test_f61.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `tests/foundations/test_20.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `F03`: Forged reviewer role never grants staff membership; another visitor's enquiry returns 404. Assert switch the presentation between customer and reviewer using the same anonymous identity and session.
- `F18`: No fake completed progress; failed poll retains last state and offers retry; hidden tabs reduce polling. Assert show persisted stages, wait reason and last update.
- `F27`: Absent evidence shown as unavailable; user HTML is escaped; scores never labelled calibrated probability. Assert show actual alias, machine configuration, supersession chain and fitment reference.
- `F32`: Negative stock blocked; stock unavailable never displayed as zero without explanation; unknown warehouse rejected. Assert show available quantity as on_hand minus reserved.
- `F37`: Missing panels show explicit empty states; stale revision disables approval; unassigned reviewer receives 404. Assert assemble current extraction, items, candidates, evidence, stock, draft and timeline.
- `F39`: Double-click publishes once; concurrent edit defeats stale approval; failed verification blocks publication. Assert approve only verified current draft.
- `F53`: No raw stack traces or keys; retry only safe idempotent action; search lexical fallback clearly reported. Assert map stable error codes to bilingual recovery guidance.
- `F61`: Exclude notes and secrets; stale or unapproved revision rejected; long Arabic names wrap without clipping; no prices or quotation title. Assert export approved revision only.

`python tools/run_checks.py --prompt 20` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for staff workspace and timeline using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `20`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-20` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(web): 20 staff workspace and timeline`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
