# F07 - Arabic and English interface
PHASE: web   DEPENDS ON: 18, 19, 20   RISK: high

## GOAL
Use a locale cookie and complete en/ar message catalogs; persist preference; set document lang and dir; isolate serials, numbers and part identifiers with bdi. Missing translation fails tests; language switch preserves enquiry ID and unsent draft; mixed Arabic identifiers remain readable.

## READ FIRST
- AGENTS.md
- docs/HANDOVER.md
- docs/CONSTRAINTS.md
- docs/ARCHITECTURE.md sections 2 and 4
- docs/TECH_SPEC.md
- docs/CONTRACTS.md
- docs/FLOW.md
- spec/file-ownership.json
- features/F07-arabic-and-english-interface.md

## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
No new package. Use the existing exact pins and committed locks; do not install a second library for this feature.

## FILES TO CREATE
- `apps/web/tests/features/f07.test.tsx`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `apps/web/lib/features/f07_arabic_and_english_interface.ts`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/components/features/LocaleSwitcher.tsx`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/messages/en.json`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/messages/ar.json`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/i18n/request.ts`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.

Typed entry contracts:

export function resolve_locale(request: F07Request): F07Result

`F07Request`: pathname: string; preference: "en" | "ar" | null.

`F07Result`: locale: "en" | "ar"; direction: "ltr" | "rtl".

Endpoint: `none`. For a public route whose owner is worker/catalogue, gateway validates role and records a durable job/event; it never executes the job inline. Internal routes use the internal token and propagated actor context.

`export function LocaleSwitcher(props: {value: F07Result | null; loading: boolean; error: ApiError | null; onAction: (request: F07Request) => Promise<void>}): React.JSX.Element`. Display loading,empty,error and success states; submit only typed identifiers,never browser-authored compatibility facts.

Implementation sequence:
1. Use a locale cookie and complete en/ar message catalogs; persist preference; set document lang and dir; isolate serials, numbers and part identifiers with bdi.
2. Missing translation fails tests; language switch preserves enquiry ID and unsent draft; mixed Arabic identifiers remain readable.

Required feature behaviours:
- F07 Arabic and English interface: Use a locale cookie and complete en/ar message catalogs; persist preference; set document lang and dir; isolate serials, numbers and part identifiers with bdi. Failure cases: Missing translation fails tests; language switch preserves enquiry ID and unsent draft; mixed Arabic identifiers remain readable.

## FILES TO MODIFY
- `apps/web/app/layout.tsx`: connect the new implementation through the existing owner; preserve callers and add regression coverage.
- `apps/web/app/page.tsx`: connect the new implementation through the existing owner; preserve callers and add regression coverage.
- `apps/web/next.config.ts`: connect the new implementation through the existing owner; preserve callers and add regression coverage.

Use locale cookie plus next-intl request configuration without renaming existing route files; locale switching preserves routes. The earlier locale-route-segment wording is replaced by cookie-based locale to avoid conflicting file paths.

## HOW IT CONNECTS
Owner: web; ARCHITECTURE.md section2. FLOW.md row `F07` identifies the entry contract and preceding owners. Required predecessors: 18, 19, 20. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `apps/web/tests/features/f07.test.tsx`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `F07`: Missing translation fails tests; language switch preserves enquiry ID and unsent draft; mixed Arabic identifiers remain readable. Assert add locale route segments and complete en/ar message catalogs.

`python tools/run_checks.py --prompt F07` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for arabic and english interface using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `F07`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-f07` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(web): F07 arabic and english interface`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
