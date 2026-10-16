# 12 - Deterministic verification
PHASE: Orchestrator   DEPENDS ON: 11   RISK: high

## GOAL
Implement named pure checks for current revision,configuration membership,candidate membership,source evidence,catalogue version,quantity and allocation. Recompute aggregate allocation across all items sharing a part and warehouse. Require nonnegative allocations,positive requested quantity and explicit shortage. Canonicalize facts using sorted JSON and decimal strings before SHA256. Persist one result for the current draft; failures contain stable codes and item IDs. Do not ask an LLM whether verification passed.

## READ FIRST
- AGENTS.md
- docs/HANDOVER.md
- docs/CONSTRAINTS.md
- docs/ARCHITECTURE.md sections 2 and 4
- docs/TECH_SPEC.md
- docs/CONTRACTS.md
- docs/FLOW.md
- spec/file-ownership.json
- features/F28-compatibility-references.md
- features/F46-verification-gate.md

## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
No new package. Use the existing exact pins and committed locks; do not install a second library for this feature.

## FILES TO CREATE
- `services/orchestrator/app/verification.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/search/tests/features/test_f28.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `services/orchestrator/tests/features/test_f46.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `tests/foundations/test_12.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.

Typed entry contracts:

def verify_facts(facts: VerifiedFacts, evidence: VerificationEvidence) -> VerificationResult; async def verify_current(enquiry_id: UUID, revision: int) -> VerificationResult.

Implementation sequence:
1. Implement named pure checks for current revision,configuration membership,candidate membership,source evidence,catalogue version,quantity and allocation.
2. Recompute aggregate allocation across all items sharing a part and warehouse.
3. Require nonnegative allocations,positive requested quantity and explicit shortage.
4. Canonicalize facts using sorted JSON and decimal strings before SHA256.
5. Persist one result for the current draft; failures contain stable codes and item IDs.
6. Do not ask an LLM whether verification passed.

Required feature behaviours:
- F28 Compatibility references: Resolve source_reference to version-specific document and page; retain citation with every candidate and approval snapshot. Failure cases: Missing source file blocks evidence viewer and flags review; mismatched version fails verification.
- F46 Verification gate: Check item/configuration/candidate membership, provenance, catalogue version, selected quantities and allocation bounds; compute canonical fact hash; store named rule results. Failure cases: Unknown part, incompatible part, stale catalogue, oversold plan and hidden extra item each fail a specific rule.

## FILES TO MODIFY
- `services/orchestrator/app/graph.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.
- `services/orchestrator/app/handlers.py`: connect the new implementation through the existing owner; preserve callers and add regression coverage.

## HOW IT CONNECTS
Owner: Orchestrator; ARCHITECTURE.md section2. FLOW.md row `12` identifies the entry contract and preceding owners. Required predecessors: 11. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `services/search/tests/features/test_f28.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `services/orchestrator/tests/features/test_f46.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `tests/foundations/test_12.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `F28`: Missing source file blocks evidence viewer and flags review; mismatched version fails verification. Assert resolve source_reference to version-specific document and page.
- `F46`: Unknown part, incompatible part, stale catalogue, oversold plan and hidden extra item each fail a specific rule. Assert check item/configuration/candidate membership, provenance, catalogue version, selected quantities and allocation bounds.

`python tools/run_checks.py --prompt 12` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for deterministic verification using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `12`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-12` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(orchestrator): 12 deterministic verification`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
