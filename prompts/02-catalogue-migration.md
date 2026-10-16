# 02 - Catalogue migration
PHASE: Database   DEPENDS ON: 01   RISK: high

## GOAL
Copy spec/sql/001_initial_schema.sql and 002_search_and_fulfilment.sql verbatim into the named migrations. This preserves numeric catalogue keys, text normalization, exclusion constraints, cycle protection and warehouse transfer days. A fresh Supabase dev project is the baseline. For an existing database, compare migration checksums and schema receipt; baseline already-applied legacy migrations rather than executing CREATE TABLE twice. No production reset command is allowed.

## READ FIRST
- AGENTS.md
- docs/HANDOVER.md
- docs/CONSTRAINTS.md
- docs/ARCHITECTURE.md sections 2 and 4
- docs/TECH_SPEC.md
- docs/CONTRACTS.md
- docs/FLOW.md
- spec/file-ownership.json
- features/F20-machine-identification.md
- features/F22-compatibility-gate.md
- features/F28-compatibility-references.md
- features/F30-old-part-numbers.md

## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
- `npm exec --yes --package=supabase@2.75.0 -- supabase --version`

Release dates and registry receipts are in spec/dependency-receipts.json. Use spec/python-requirements.lock and spec/pnpm-lock.yaml as resolution references; do not claim installing these packages proves application compatibility.

## FILES TO CREATE
- `supabase/config.toml`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `supabase/migrations/20261011000100_legacy_catalogue.sql`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `supabase/migrations/20261011000200_legacy_search.sql`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tests/foundations/test_02.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.

Typed entry contracts:

async def apply_catalogue_schema(dsn: str) -> None; schema comparison is owned by collect_schema_receipt in prompt03.

Implementation sequence:
1. Copy spec/sql/001_initial_schema.sql and 002_search_and_fulfilment.sql verbatim into the named migrations.
2. This preserves numeric catalogue keys, text normalization, exclusion constraints, cycle protection and warehouse transfer days.
3. A fresh Supabase dev project is the baseline.
4. For an existing database, compare migration checksums and schema receipt; baseline already-applied legacy migrations rather than executing CREATE TABLE twice.
5. No production reset command is allowed.

Required feature behaviours:
- F20 Machine identification: Preserve identify_machine logic for model, serial and rating; return resolved configuration or explicit missing/ambiguous status; normalize numeric serial only after preserving input. Failure cases: Boundary serials match exactly one configuration; overlapping ranges fail database insertion; conflicting hints never silently override.
- F22 Compatibility gate: Fetch authoritative fitment set first; rank only members; carry source_reference and catalogue version through every candidate. Failure cases: A perfect lexical match outside fitment is absent; empty fitment returns unavailable; blank provenance cannot be published.
- F28 Compatibility references: Resolve source_reference to version-specific document and page; retain citation with every candidate and approval snapshot. Failure cases: Missing source file blocks evidence viewer and flags review; mismatched version fails verification.
- F30 Old part numbers: Follow supersession chain with cycle protection; display old and current numbers; verify current successor has explicit fitment for resolved configuration. Failure cases: Cycles rejected; inactive terminal part returns unavailable; inherited compatibility without source is rejected.

- `tools/apply_catalogue_schema.py`: `async def apply_catalogue_schema(dsn: str) -> None: apply the two immutable migration files through the Supabase migration runner; refuse a production reset.`

## FILES TO MODIFY
No existing runtime file requires modification beyond the documentation updates and package manifests named here.

## HOW IT CONNECTS
Owner: Database; ARCHITECTURE.md section2. FLOW.md row `02` identifies the entry contract and preceding owners. Required predecessors: 01. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `tests/foundations/test_02.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `F20`: Boundary serials match exactly one configuration; overlapping ranges fail database insertion; conflicting hints never silently override. Assert preserve identify_machine logic for model, serial and rating.
- `F22`: A perfect lexical match outside fitment is absent; empty fitment returns unavailable; blank provenance cannot be published. Assert fetch authoritative fitment set first.
- `F28`: Missing source file blocks evidence viewer and flags review; mismatched version fails verification. Assert resolve source_reference to version-specific document and page.
- `F30`: Cycles rejected; inactive terminal part returns unavailable; inherited compatibility without source is rejected. Assert follow supersession chain with cycle protection.

`python tools/run_checks.py --prompt 02` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for catalogue migration using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `02`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-02` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(database): 02 catalogue migration`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
