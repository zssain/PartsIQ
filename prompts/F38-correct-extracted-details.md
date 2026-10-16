# F38 - Correct extracted details
PHASE: orchestrator   DEPENDS ON: 09, 14, 20   RISK: high

## GOAL
Lock enquiry; compare expected revision; apply typed allowed corrections; increment revision; invalidate derived selections/draft/approval; enqueue recomputation; record before and after. Unknown field rejected; old revision returns 409; correction cannot directly set approved status or invent candidate facts.

## READ FIRST
- AGENTS.md
- docs/HANDOVER.md
- docs/CONSTRAINTS.md
- docs/ARCHITECTURE.md sections 2 and 4
- docs/TECH_SPEC.md
- docs/CONTRACTS.md
- docs/FLOW.md
- spec/file-ownership.json
- features/F38-correct-extracted-details.md

## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
No new package. Use the existing exact pins and committed locks; do not install a second library for this feature.

## FILES TO CREATE
- `services/orchestrator/tests/features/test_f38.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `services/orchestrator/app/features/f38_correct_extracted_details.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/components/features/CorrectionEditor.tsx`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/lib/features/f38_correct_extracted_details.ts`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.

Typed entry contracts:

async def correct_extraction(actor: ActorContext, request: F38Request) -> F38Result

`F38Request`: change: RevisionRequest.

`F38Result`: enquiry: EnquiryView.

Endpoint: `POST /internal/enquiries/correct`. For a public route whose owner is worker/catalogue, gateway validates role and records a durable job/event; it never executes the job inline. Internal routes use the internal token and propagated actor context.

`export function CorrectionEditor(props: {value: F38Result | null; loading: boolean; error: ApiError | null; onAction: (request: F38Request) => Promise<void>}): React.JSX.Element`. Display loading,empty,error and success states; submit only typed identifiers,never browser-authored compatibility facts.

Implementation sequence:
1. Lock enquiry; compare expected revision; apply typed allowed corrections; increment revision; invalidate derived selections/draft/approval; enqueue recomputation; record before and after.
2. Unknown field rejected; old revision returns 409; correction cannot directly set approved status or invent candidate facts.

Required feature behaviours:
- F38 Correct extracted details: Lock enquiry; compare expected revision; apply typed allowed corrections; increment revision; invalidate derived selections/draft/approval; enqueue recomputation; record before and after. Failure cases: Unknown field rejected; old revision returns 409; correction cannot directly set approved status or invent candidate facts.

## FILES TO MODIFY
- `apps/web/app/staff/enquiries/[id]/page.tsx`: connect the new implementation through the existing owner; preserve callers and add regression coverage.
- `services/orchestrator/app/handlers.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.
- `services/orchestrator/app/routes.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.

Gateway adapter services/gateway/app/features/f38_correction_routes.py exposes POST /v1/staff/enquiries/{id}/corrections and calls internal orchestrator correction endpoint after require_access(review). Register in api_v1.py.

- `services/gateway/app/api_v1.py`: register this prompt's route or handler.

## HOW IT CONNECTS
Owner: orchestrator; ARCHITECTURE.md section2. FLOW.md row `F38` identifies the entry contract and preceding owners. Required predecessors: 09, 14, 20. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `services/orchestrator/tests/features/test_f38.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `F38`: Unknown field rejected; old revision returns 409; correction cannot directly set approved status or invent candidate facts. Assert lock enquiry.

`python tools/run_checks.py --prompt F38` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for correct extracted details using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `F38`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-f38` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(orchestrator): F38 correct extracted details`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
