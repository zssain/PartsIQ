# 08 - Enquiry intake and limits
PHASE: Gateway   DEPENDS ON: 07   RISK: high

## GOAL
Create enquiry,first message,revision snapshot and workflow event atomically. Accept Idempotency-Key UUID; repeated identical input returns existing resource, different payload returns 409. Generate object names server-side. Preserve legacy middleware for size limits and traversal blocking. Redis rate limiter rejects when Redis unavailable. Gateway writes intake/session/staff CRUD; orchestrator owns derived facts and publication. Return 202 after durable commit, not after OCR or language calls.

## READ FIRST
- AGENTS.md
- docs/HANDOVER.md
- docs/CONSTRAINTS.md
- docs/ARCHITECTURE.md sections 2 and 4
- docs/TECH_SPEC.md
- docs/CONTRACTS.md
- docs/FLOW.md
- spec/file-ownership.json
- features/F13-private-uploads.md

## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
No new package. Use the existing exact pins and committed locks; do not install a second library for this feature.

## FILES TO CREATE
- `services/gateway/app/enquiries.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/gateway/app/uploads.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/gateway/app/api_v1.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tests/foundations/test_08.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.

Typed entry contracts:

async def create_enquiry(actor: ActorContext, body: EnquiryCreate, key: UUID) -> EnquiryView; async def add_message(actor: ActorContext, enquiry_id: UUID, body: MessageCreate, key: UUID) -> MessageView; async def confirm_upload(actor: ActorContext, attachment_id: UUID) -> AttachmentView.

Implementation sequence:
1. Create enquiry,first message,revision snapshot and workflow event atomically.
2. Accept Idempotency-Key UUID; repeated identical input returns existing resource, different payload returns 409.
3. Generate object names server-side.
4. Preserve legacy middleware for size limits and traversal blocking.
5. Redis rate limiter rejects when Redis unavailable.
6. Gateway writes intake/session/staff CRUD; orchestrator owns derived facts and publication.
7. Return 202 after durable commit, not after OCR or language calls.

Required feature behaviours:
- F13 Private uploads: Create pending attachment and unique object path; use signed upload; validate actual bytes and magic type after confirmation; strip EXIF and cap decoded pixels before OCR. Failure cases: Wrong MIME, oversized content, image decompression bomb, duplicate confirmation and nonexistent object handled explicitly.

## FILES TO MODIFY
- `services/gateway/app/main.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.
- `services/gateway/app/proxy.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.
- `services/gateway/app/rate_limit.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.

## HOW IT CONNECTS
Owner: Gateway; ARCHITECTURE.md section2. FLOW.md row `08` identifies the entry contract and preceding owners. Required predecessors: 07. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `tests/foundations/test_08.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `F13`: Wrong MIME, oversized content, image decompression bomb, duplicate confirmation and nonexistent object handled explicitly. Assert create pending attachment and unique object path.

`python tools/run_checks.py --prompt 08` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for enquiry intake and limits using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `08`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-08` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(gateway): 08 enquiry intake and limits`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
