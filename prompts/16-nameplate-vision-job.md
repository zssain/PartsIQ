# 16 - Nameplate vision job
PHASE: Worker   DEPENDS ON: 15   RISK: high

## GOAL
Decode validated image with pixel cap,strip EXIF,normalize orientation and prepare bounded image. Use OpenAI vision via shared client. Extract model_text,serial_text and issues only. Do not use model confidence as accuracy. Persist extraction,mark confirmation required and append workflow event using lease fencing. Partial OCR asks for manual entry. Handle budget exhaustion as recoverable staff/manual-input route.

## READ FIRST
- AGENTS.md
- docs/HANDOVER.md
- docs/CONSTRAINTS.md
- docs/ARCHITECTURE.md sections 2 and 4
- docs/TECH_SPEC.md
- docs/CONTRACTS.md
- docs/FLOW.md
- spec/file-ownership.json
- features/F14-nameplate-ocr.md
- features/F15-ocr-confirmation.md

## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
No new package. Use the existing exact pins and committed locks; do not install a second library for this feature.

## FILES TO CREATE
- `services/worker/app/jobs/nameplate.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/worker/tests/features/test_f14.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `tests/foundations/test_16.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.

Typed entry contracts:

async def read_nameplate(job: JobLease, image: bytes) -> NameplateResult; def validate_image(image: bytes, media_type: str) -> ImageInfo.

Implementation sequence:
1. Decode validated image with pixel cap,strip EXIF,normalize orientation and prepare bounded image.
2. Use OpenAI vision via shared client.
3. Extract model_text,serial_text and issues only.
4. Do not use model confidence as accuracy.
5. Persist extraction,mark confirmation required and append workflow event using lease fencing.
6. Partial OCR asks for manual entry.
7. Handle budget exhaustion as recoverable staff/manual-input route.

Required feature behaviours:
- F14 Nameplate OCR: Read validated nameplate via OpenAI vision; return model_text,serial_text,issues and source attachment; persist result only with current lease and revision. Failure cases: Unreadable fields remain null; vision instructions in photo are untrusted; timeout is bounded and creates recoverable status.
- F15 OCR confirmation: Show cropped or original nameplate beside extracted identifiers; require user confirm or correction; record actor and time; preserve leading zeros in serial text. Failure cases: Unconfirmed OCR never authorizes matching; blank corrected serial triggers missing-serial flow; stale confirmation returns 409.

Exact package markers and bundled assets created by this step:
- `services/worker/app/jobs/__init__.py`

- `services/gateway/app/ocr_confirmation.py`: `async def confirm_extraction(actor: ActorContext, enquiry_id: UUID, request: ConfirmExtraction) -> EnquiryView: authorize owner or assigned reviewer; call orchestrator revise; atomically record confirmation after revision comparison. POST /v1/enquiries/{id}/extractions/{extraction_id}/confirm.`

## FILES TO MODIFY
- `services/worker/app/dispatcher.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.

- `services/gateway/app/api_v1.py`: register this prompt's route or handler.

## HOW IT CONNECTS
Owner: Worker; ARCHITECTURE.md section2. FLOW.md row `16` identifies the entry contract and preceding owners. Required predecessors: 15. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `services/worker/tests/features/test_f14.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `tests/foundations/test_16.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `F14`: Unreadable fields remain null; vision instructions in photo are untrusted; timeout is bounded and creates recoverable status. Assert read validated nameplate via openai vision.
- `F15`: Unconfirmed OCR never authorizes matching; blank corrected serial triggers missing-serial flow; stale confirmation returns 409. Assert show cropped or original nameplate beside extracted identifiers.

`python tools/run_checks.py --prompt 16` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for nameplate vision job using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `16`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-16` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(worker): 16 nameplate vision job`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
