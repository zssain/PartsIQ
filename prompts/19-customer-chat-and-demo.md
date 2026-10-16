# 19 - Customer chat and demo
PHASE: Web   DEPENDS ON: 18   RISK: high

## GOAL
Implement four scenario cards,chat,private upload progress,OCR confirmation and code-owned clarification display. Preserve unsent text when recoverable request fails. Poll enquiry with AbortController and bounded backoff; distinguish waiting customer/staff. Reset clears client cache and old generation. Only approved recommendation messages appear; customer messages and safe status/clarification messages remain visible without approval.

## READ FIRST
- AGENTS.md
- docs/HANDOVER.md
- docs/CONSTRAINTS.md
- docs/ARCHITECTURE.md sections 2 and 4
- docs/TECH_SPEC.md
- docs/CONTRACTS.md
- docs/FLOW.md
- spec/file-ownership.json
- features/F02-demo-scenarios-and-assets.md
- features/F03-demo-role-switching.md
- features/F05-demo-reset.md
- features/F09-bilingual-chat.md
- features/F11-clarifying-questions.md
- features/F13-private-uploads.md
- features/F15-ocr-confirmation.md
- features/F18-progress-timeline.md
- features/F53-graceful-failures.md

## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
No new package. Use the existing exact pins and committed locks; do not install a second library for this feature.

## FILES TO CREATE
- `apps/web/app/chat/[id]/page.tsx`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/app/demo/page.tsx`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/components/chat/Chat.tsx`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/components/chat/UploadCard.tsx`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/components/chat/OcrConfirmation.tsx`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/components/chat/Progress.tsx`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tests/acceptance/test_f02.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `services/gateway/tests/features/test_f05.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `services/orchestrator/tests/features/test_f09.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `services/orchestrator/tests/features/test_f11.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `services/gateway/tests/features/test_f13.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `apps/web/tests/features/f15.test.tsx`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `tests/foundations/test_19.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.

Typed entry contracts:

export function Chat(props: {enquiryId: string}): React.JSX.Element; export function OcrConfirmation(props: {extraction: NameplateResult; onConfirm: (value: ConfirmExtraction) => Promise<void>}): React.JSX.Element.

Implementation sequence:
1. Implement four scenario cards,chat,private upload progress,OCR confirmation and code-owned clarification display.
2. Preserve unsent text when recoverable request fails.
3. Poll enquiry with AbortController and bounded backoff; distinguish waiting customer/staff.
4. Reset clears client cache and old generation.
5. Only approved recommendation messages appear; customer messages and safe status/clarification messages remain visible without approval.

Required feature behaviours:
- F02 Demo scenarios and assets: Seed four deterministic scenarios: mixed-language photo, missing serial, incompatible part, local shortage; derive identifiers from seed 42; validate expected outcomes against generated records. Failure cases: Reject a scenario whose expected part lacks compatibility; reject stock claims not supported by fixture quantities.
- F03 Demo role switching: Switch the presentation between customer and reviewer using the same anonymous identity and session; authorize review only for enquiries belonging to that active session. Failure cases: Forged reviewer role never grants staff membership; another visitor's enquiry returns 404.
- F05 Demo reset: Lock session; increment generation; cancel unfinished jobs from prior generation; enqueue Storage cleanup; keep minimal audit; create fresh scenario enquiries on explicit selection. Failure cases: Late OCR from old generation cannot update current data; repeated reset idempotency key returns the same generation.
- F09 Bilingual chat: Accept Arabic, English and mixed text; preserve original message; detect preferred reply locale; render customer messages immediately after successful persistence. Failure cases: Empty and oversized input returns validation error; HTML is escaped; retry does not duplicate a message.
- F11 Clarifying questions: Use controller reason codes to choose code-owned bilingual questions; persist interrupt; associate answer with item; rerun affected resolution only. Failure cases: No final recommendation before approval; contradictory answer requires confirmation; repeat event creates one question.
- F13 Private uploads: Create pending attachment and unique object path; use signed upload; validate actual bytes and magic type after confirmation; strip EXIF and cap decoded pixels before OCR. Failure cases: Wrong MIME, oversized content, image decompression bomb, duplicate confirmation and nonexistent object handled explicitly.
- F15 OCR confirmation: Show cropped or original nameplate beside extracted identifiers; require user confirm or correction; record actor and time; preserve leading zeros in serial text. Failure cases: Unconfirmed OCR never authorizes matching; blank corrected serial triggers missing-serial flow; stale confirmation returns 409.
- F18 Progress timeline: Show persisted stages, wait reason and last update; poll with bounded backoff; reconnect using server state; separate waiting for customer from waiting for staff. Failure cases: No fake completed progress; failed poll retains last state and offers retry; hidden tabs reduce polling.
- F53 Graceful failures: Map stable error codes to bilingual recovery guidance; distinguish validation,quota,service outage and staff-required states; preserve user input. Failure cases: No raw stack traces or keys; retry only safe idempotent action; search lexical fallback clearly reported.

## FILES TO MODIFY
No existing runtime file requires modification beyond the documentation updates and package manifests named here.

## HOW IT CONNECTS
Owner: Web; ARCHITECTURE.md section2. FLOW.md row `19` identifies the entry contract and preceding owners. Required predecessors: 18. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `tests/acceptance/test_f02.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `services/gateway/tests/features/test_f05.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `services/orchestrator/tests/features/test_f09.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `services/orchestrator/tests/features/test_f11.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `services/gateway/tests/features/test_f13.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `apps/web/tests/features/f15.test.tsx`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `tests/foundations/test_19.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `F02`: Reject a scenario whose expected part lacks compatibility; reject stock claims not supported by fixture quantities. Assert seed four deterministic scenarios: mixed-language photo, missing serial, incompatible part, local shortage.
- `F03`: Forged reviewer role never grants staff membership; another visitor's enquiry returns 404. Assert switch the presentation between customer and reviewer using the same anonymous identity and session.
- `F05`: Late OCR from old generation cannot update current data; repeated reset idempotency key returns the same generation. Assert lock session.
- `F09`: Empty and oversized input returns validation error; HTML is escaped; retry does not duplicate a message. Assert accept arabic, english and mixed text.
- `F11`: No final recommendation before approval; contradictory answer requires confirmation; repeat event creates one question. Assert use controller reason codes to choose code-owned bilingual questions.
- `F13`: Wrong MIME, oversized content, image decompression bomb, duplicate confirmation and nonexistent object handled explicitly. Assert create pending attachment and unique object path.
- `F15`: Unconfirmed OCR never authorizes matching; blank corrected serial triggers missing-serial flow; stale confirmation returns 409. Assert show cropped or original nameplate beside extracted identifiers.
- `F18`: No fake completed progress; failed poll retains last state and offers retry; hidden tabs reduce polling. Assert show persisted stages, wait reason and last update.
- `F53`: No raw stack traces or keys; retry only safe idempotent action; search lexical fallback clearly reported. Assert map stable error codes to bilingual recovery guidance.

`python tools/run_checks.py --prompt 19` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for customer chat and demo using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `19`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-19` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(web): 19 customer chat and demo`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
