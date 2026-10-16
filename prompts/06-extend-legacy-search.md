# 06 - Extend legacy search
PHASE: Search   DEPENDS ON: 05   RISK: high

## GOAL
Characterize current identify_machine,LexicalScorer,SearchService and plan_fulfilment first. Keep identification.py,lexical.py,fulfilment.py,repository.py,service.py,routes.py and schemas.py. Add internal token authentication to routes. Preserve weighted semantic fusion and lexical fallback. Require terminal supersession part to have explicit fitment; fix margin calculation before result truncation. Search-owned encoder reads a validated published version and upserts vectors with source hash. Use one search process and one encoder; readiness reports lexical readiness and semantic capability separately.

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
- features/F21-machine-mismatch-detection.md
- features/F22-compatibility-gate.md
- features/F23-aliases-and-typo-matching.md
- features/F24-semantic-retrieval.md
- features/F25-ranked-candidates.md
- features/F26-ambiguity-handling.md
- features/F27-match-explanations.md
- features/F28-compatibility-references.md
- features/F30-old-part-numbers.md
- features/F32-warehouse-stock.md
- features/F33-fulfilment-planning.md
- features/F34-transfer-estimates.md

## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
- `uv pip install sentence-transformers==5.2.3 transformers==4.57.6 torch==2.10.0+cpu numpy==2.4.2` in the task-specific development environment. Add the identical pins to the owning workspace project; synchronize from the shared workspace lock for application execution.

Release dates and registry receipts are in spec/dependency-receipts.json. Use spec/python-requirements.lock and spec/pnpm-lock.yaml as resolution references; do not claim installing these packages proves application compatibility.

CPU wheel command: `uv pip install torch==2.10.0+cpu --index-url https://download.pytorch.org/whl/cpu`. Configure the root uv workspace with an explicit pytorch-cpu index for torch only. Never install CUDA wheels on the EC2 CPU profile. The base release date is2026-01-21; wheel/index receipt is captured by dependency resolution.

## FILES TO CREATE
- `services/search/app/embedding_ingestion.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/search/tests/test_characterization.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/search/tests/features/test_f20.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `services/search/tests/features/test_f21.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `services/search/tests/features/test_f22.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `services/search/tests/features/test_f23.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `services/search/tests/features/test_f24.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `services/search/tests/features/test_f25.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `services/search/tests/features/test_f30.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `services/search/tests/features/test_f33.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `services/search/tests/features/test_f34.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `tests/foundations/test_06.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.

Typed entry contracts:

async def embed_version(version_id: UUID, batch_size: int=16) -> EmbeddingReceipt; preserve SearchService.identify(request: IdentifyRequest) -> IdentifyResponse and SearchService.search_parts(request: PartSearchRequest) -> PartSearchResponse.

Implementation sequence:
1. Characterize current identify_machine,LexicalScorer,SearchService and plan_fulfilment first.
2. Keep identification.py,lexical.py,fulfilment.py,repository.py,service.py,routes.py and schemas.py.
3. Add internal token authentication to routes.
4. Preserve weighted semantic fusion and lexical fallback.
5. Require terminal supersession part to have explicit fitment; fix margin calculation before result truncation.
6. Search-owned encoder reads a validated published version and upserts vectors with source hash.
7. Use one search process and one encoder; readiness reports lexical readiness and semantic capability separately.

Required feature behaviours:
- F20 Machine identification: Preserve identify_machine logic for model, serial and rating; return resolved configuration or explicit missing/ambiguous status; normalize numeric serial only after preserving input. Failure cases: Boundary serials match exactly one configuration; overlapping ranges fail database insertion; conflicting hints never silently override.
- F21 Machine mismatch detection: Compare model and serial together; return mismatch reason with safe next question; prevent retrieval while identity unresolved. Failure cases: Valid serial of a different model does not match requested model; nonnumeric serial handled without crashing.
- F22 Compatibility gate: Fetch authoritative fitment set first; rank only members; carry source_reference and catalogue version through every candidate. Failure cases: A perfect lexical match outside fitment is absent; empty fitment returns unavailable; blank provenance cannot be published.
- F23 Aliases and typo matching: Preserve Arabic normalization, part-number keys, phrase scoring and fuzzy token matching; remove machine terms using resolved model context. Failure cases: Arabic part words are not removed as machine words; exact part number outranks unrelated fuzzy alias; normalization parity test matches SQL.
- F24 Semantic retrieval: Load one BGE-M3 encoder per search process; use normalized 1024-d vectors; retain legacy weighted fusion; fall back to lexical on unavailable embedding path. Failure cases: Wrong dimension rejected; no model loaded in worker; no semantic candidate outside compatible IDs.
- F25 Ranked candidates: Return top candidates with lexical/semantic evidence and deterministic tie order; compute runner-up margin before applying response limit. Failure cases: Limit one still reports ambiguity; empty set returns no candidate; NaN scores rejected.
- F26 Ambiguity handling: Use tested score and margin thresholds in code; ask customer to distinguish fuel filter versus separator; allow staff to select only verified candidates. Failure cases: LLM cannot override low confidence; unavailable candidate choice returns 409; thresholds evaluated on labelled cases.
- F27 Match explanations: Show actual alias, machine configuration, supersession chain and fitment reference; derive explanations from search evidence rather than invented model prose. Failure cases: Absent evidence shown as unavailable; user HTML is escaped; scores never labelled calibrated probability.
- F28 Compatibility references: Resolve source_reference to version-specific document and page; retain citation with every candidate and approval snapshot. Failure cases: Missing source file blocks evidence viewer and flags review; mismatched version fails verification.
- F30 Old part numbers: Follow supersession chain with cycle protection; display old and current numbers; verify current successor has explicit fitment for resolved configuration. Failure cases: Cycles rejected; inactive terminal part returns unavailable; inherited compatibility without source is rejected.
- F32 Warehouse stock: Show available quantity as on_hand minus reserved; include timestamp and warehouse name; keep display and planner using same snapshot. Failure cases: Negative stock blocked; stock unavailable never displayed as zero without explanation; unknown warehouse rejected.
- F33 Fulfilment planning: Allocate local stock first then reachable warehouses deterministically; compute shortage; use quantity units; do not reserve stock or create orders. Failure cases: Total allocations never exceed request or stock; fractional quantities respect unit policy; unavailable transfer route cannot be invented.
- F34 Transfer estimates: Carry integer transfer_days from approved route; show estimate and source warehouse; local availability means zero transfer days. Failure cases: No route gives unknown/unavailable plan rather than invented one-day promise; estimate labelled non-guaranteed.

## FILES TO MODIFY
- `libs/partsiq_common/partsiq_common/embeddings.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.
- `services/search/Dockerfile`: connect the new implementation through the existing owner; preserve callers and add regression coverage.
- `services/search/app/config.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.
- `services/search/app/main.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.
- `services/search/app/repository.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.
- `services/search/app/routes.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.
- `services/search/app/schemas.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.
- `services/search/app/service.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.
- `tools/catalog/catalog/embedder.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.

## HOW IT CONNECTS
Owner: Search; ARCHITECTURE.md section2. FLOW.md row `06` identifies the entry contract and preceding owners. Required predecessors: 05. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `services/search/tests/features/test_f20.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `services/search/tests/features/test_f21.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `services/search/tests/features/test_f22.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `services/search/tests/features/test_f23.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `services/search/tests/features/test_f24.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `services/search/tests/features/test_f25.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `services/search/tests/features/test_f30.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `services/search/tests/features/test_f33.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `services/search/tests/features/test_f34.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `tests/foundations/test_06.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `F20`: Boundary serials match exactly one configuration; overlapping ranges fail database insertion; conflicting hints never silently override. Assert preserve identify_machine logic for model, serial and rating.
- `F21`: Valid serial of a different model does not match requested model; nonnumeric serial handled without crashing. Assert compare model and serial together.
- `F22`: A perfect lexical match outside fitment is absent; empty fitment returns unavailable; blank provenance cannot be published. Assert fetch authoritative fitment set first.
- `F23`: Arabic part words are not removed as machine words; exact part number outranks unrelated fuzzy alias; normalization parity test matches SQL. Assert preserve arabic normalization, part-number keys, phrase scoring and fuzzy token matching.
- `F24`: Wrong dimension rejected; no model loaded in worker; no semantic candidate outside compatible IDs. Assert load one bge-m3 encoder per search process.
- `F25`: Limit one still reports ambiguity; empty set returns no candidate; NaN scores rejected. Assert return top candidates with lexical/semantic evidence and deterministic tie order.
- `F26`: LLM cannot override low confidence; unavailable candidate choice returns 409; thresholds evaluated on labelled cases. Assert use tested score and margin thresholds in code.
- `F27`: Absent evidence shown as unavailable; user HTML is escaped; scores never labelled calibrated probability. Assert show actual alias, machine configuration, supersession chain and fitment reference.
- `F28`: Missing source file blocks evidence viewer and flags review; mismatched version fails verification. Assert resolve source_reference to version-specific document and page.
- `F30`: Cycles rejected; inactive terminal part returns unavailable; inherited compatibility without source is rejected. Assert follow supersession chain with cycle protection.
- `F32`: Negative stock blocked; stock unavailable never displayed as zero without explanation; unknown warehouse rejected. Assert show available quantity as on_hand minus reserved.
- `F33`: Total allocations never exceed request or stock; fractional quantities respect unit policy; unavailable transfer route cannot be invented. Assert allocate local stock first then reachable warehouses deterministically.
- `F34`: No route gives unknown/unavailable plan rather than invented one-day promise; estimate labelled non-guaranteed. Assert carry integer transfer_days from approved route.

`python tools/run_checks.py --prompt 06` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for extend legacy search using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `06`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-06` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(search): 06 extend legacy search`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
