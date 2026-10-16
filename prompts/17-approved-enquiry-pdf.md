# 17 - Approved enquiry PDF
PHASE: Worker   DEPENDS ON: 16   RISK: high

## GOAL
Load approved immutable revision and decision; deny live draft export. Use trusted HTML template with local brand/fonts and Chromium. Disable external browser requests,JavaScript and arbitrary file access. Render Arabic with RTL and identifiers isolated LTR. Include synthetic-demo watermark and non-guaranteed transfer estimate. Hash output,upload private object and persist export record under lease token. Gateway returns signed URL only after authorization.

## READ FIRST
- AGENTS.md
- docs/HANDOVER.md
- docs/CONSTRAINTS.md
- docs/ARCHITECTURE.md sections 2 and 4
- docs/TECH_SPEC.md
- docs/CONTRACTS.md
- docs/FLOW.md
- spec/file-ownership.json
- features/F61-enquiry-pdf.md

## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
- `uv pip install Jinja2==3.1.6 playwright==1.58.0 pypdf==6.8.0` in the task-specific development environment. Add the identical pins to the owning workspace project; synchronize from the shared workspace lock for application execution.

Release dates and registry receipts are in spec/dependency-receipts.json. Use spec/python-requirements.lock and spec/pnpm-lock.yaml as resolution references; do not claim installing these packages proves application compatibility.

## FILES TO CREATE
- `services/worker/app/jobs/export_pdf.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/worker/app/templates/enquiry_summary.html`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tests/foundations/test_17.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.

Typed entry contracts:

async def export_enquiry(job: JobLease, request: ExportRequest) -> ExportResult; def render_export_html(snapshot: ApprovedSnapshot) -> str.

Implementation sequence:
1. Load approved immutable revision and decision; deny live draft export.
2. Use trusted HTML template with local brand/fonts and Chromium.
3. Disable external browser requests,JavaScript and arbitrary file access.
4. Render Arabic with RTL and identifiers isolated LTR.
5. Include synthetic-demo watermark and non-guaranteed transfer estimate.
6. Hash output,upload private object and persist export record under lease token.
7. Gateway returns signed URL only after authorization.

Required feature behaviours:
- F61 Enquiry PDF: Export approved revision only; render logo,bilingual customer text,verified selections,estimates and references; embed Arabic fonts; store private object and signed download. Failure cases: Exclude notes and secrets; stale or unapproved revision rejected; long Arabic names wrap without clipping; no prices or quotation title.

Exact package markers and bundled assets created by this step:
- `services/worker/app/static/brand/fonts/NotoNaskhArabic-OFL.txt`
- `services/worker/app/static/brand/fonts/NotoNaskhArabic.ttf`
- `services/worker/app/static/brand/fonts/NotoSans-OFL.txt`
- `services/worker/app/static/brand/fonts/NotoSans.ttf`
- `services/worker/app/static/brand/fonts/NotoSansArabic-OFL.txt`
- `services/worker/app/static/brand/fonts/NotoSansArabic.ttf`
- `services/worker/app/static/brand/logo-original.png`

## FILES TO MODIFY
- `services/worker/app/dispatcher.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.

## HOW IT CONNECTS
Owner: Worker; ARCHITECTURE.md section2. FLOW.md row `17` identifies the entry contract and preceding owners. Required predecessors: 16. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `tests/foundations/test_17.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `F61`: Exclude notes and secrets; stale or unapproved revision rejected; long Arabic names wrap without clipping; no prices or quotation title. Assert export approved revision only.

`python tools/run_checks.py --prompt 17` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for approved enquiry pdf using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `17`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-17` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(worker): 17 approved enquiry pdf`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
