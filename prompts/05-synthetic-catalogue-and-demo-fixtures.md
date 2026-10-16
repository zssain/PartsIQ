# 05 - Synthetic catalogue and demo fixtures
PHASE: Catalogue   DEPENDS ON: 04   RISK: high

## GOAL
Use existing tools/catalog/catalog generator and validator with seed 42. Preserve loader identity mapping and source labels. Generate four scenario fixtures by selecting real generated records with required properties, not hardcoded illustrative numbers. Generate synthetic nameplate PNGs and cited PDF pages with manifests of hashes. Fail generation when an expected outcome cannot be demonstrated. Base loading creates the initial published catalogue_versions row,immutable catalogue_records snapshot and catalogue_evidence rows from generated manifests in the same controlled seed transaction. Base catalogue loading does not instantiate BGE-M3; embedding is deferred to 06.

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

## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
- `uv pip install Pillow==12.1.1` in the task-specific development environment. Add the identical pins to the owning workspace project; synchronize from the shared workspace lock for application execution.

Release dates and registry receipts are in spec/dependency-receipts.json. Use spec/python-requirements.lock and spec/pnpm-lock.yaml as resolution references; do not claim installing these packages proves application compatibility.

## FILES TO CREATE
- `tools/demo/build_scenarios.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tools/demo/scenarios.json`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tools/demo/nameplates/manifest.json`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tools/demo/catalogue_evidence/manifest.json`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tools/demo/render_assets.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tools/demo/scenarios/mixed_photo.json`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tools/demo/scenarios/missing_serial.json`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tools/demo/scenarios/incompatible_number.json`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tools/demo/scenarios/local_shortage.json`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tests/foundations/test_05.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.

Typed entry contracts:

def build_scenarios(dataset: CatalogDataset) -> list[DemoScenario]; def render_nameplate(model: str, serial: str, destination: Path) -> None; def validate_scenarios(scenarios: list[DemoScenario], dataset: CatalogDataset) -> list[str].

Implementation sequence:
1. Use existing tools/catalog/catalog generator and validator with seed 42.
2. Preserve loader identity mapping and source labels.
3. Generate four scenario fixtures by selecting real generated records with required properties, not hardcoded illustrative numbers.
4. Generate synthetic nameplate PNGs and cited PDF pages with manifests of hashes.
5. Fail generation when an expected outcome cannot be demonstrated.
6. Base loading creates the initial published catalogue_versions row,immutable catalogue_records snapshot and catalogue_evidence rows from generated manifests in the same controlled seed transaction. Base catalogue loading does not instantiate BGE-M3; embedding is deferred to 06.

Required feature behaviours:
- F02 Demo scenarios and assets: Seed four deterministic scenarios: mixed-language photo, missing serial, incompatible part, local shortage; derive identifiers from seed 42; validate expected outcomes against generated records. Failure cases: Reject a scenario whose expected part lacks compatibility; reject stock claims not supported by fixture quantities.

## FILES TO MODIFY
No existing runtime file requires modification beyond the documentation updates and package manifests named here.

## HOW IT CONNECTS
Owner: Catalogue; ARCHITECTURE.md section2. FLOW.md row `05` identifies the entry contract and preceding owners. Required predecessors: 04. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `tests/foundations/test_05.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `F02`: Reject a scenario whose expected part lacks compatibility; reject stock claims not supported by fixture quantities. Assert seed four deterministic scenarios: mixed-language photo, missing serial, incompatible part, local shortage.

`python tools/run_checks.py --prompt 05` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for synthetic catalogue and demo fixtures using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `05`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-05` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(catalogue): 05 synthetic catalogue and demo fixtures`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
