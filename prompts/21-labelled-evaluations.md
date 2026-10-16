# 21 - Labelled evaluations
PHASE: Quality   DEPENDS ON: F48   RISK: high

## GOAL
Build labelled expected outcomes from deterministic catalogue fixtures. Include all four demo scenarios,serial endpoints,Arabic normalization,typos,successor fitment,close scores,multiitem stock and malicious instructions. Separate deterministic checks from optional live-model evaluation. Deterministic suite must not require OpenAI credit. Record dataset hash,git SHA and model ID for live runs. Accuracy denominator excludes unreadable/unlabelled cases and reports abstention separately.

## READ FIRST
- AGENTS.md
- docs/HANDOVER.md
- docs/CONSTRAINTS.md
- docs/ARCHITECTURE.md sections 2 and 4
- docs/TECH_SPEC.md
- docs/CONTRACTS.md
- docs/FLOW.md
- spec/file-ownership.json
- features/F62-labelled-evaluations.md

## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
No new package. Use the existing exact pins and committed locks; do not install a second library for this feature.

## FILES TO CREATE
- `tools/evals/run.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tests/evals/cases.json`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tests/evals/test_scenarios.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tools/evals/__init__.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tests/acceptance/test_f62.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `tests/foundations/test_21.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.

Typed entry contracts:

def evaluate_case(case: EvalCase, actual: EvalOutput) -> EvalResult; async def run_suite(cases: list[EvalCase], live: bool=False) -> EvalRun.

Implementation sequence:
1. Build labelled expected outcomes from deterministic catalogue fixtures.
2. Include all four demo scenarios,serial endpoints,Arabic normalization,typos,successor fitment,close scores,multiitem stock and malicious instructions.
3. Separate deterministic checks from optional live-model evaluation.
4. Deterministic suite must not require OpenAI credit.
5. Record dataset hash,git SHA and model ID for live runs.
6. Accuracy denominator excludes unreadable/unlabelled cases and reports abstention separately.

Required feature behaviours:
- F62 Labelled evaluations: Include four demos plus Arabic,typo,serial-boundary,ambiguity,stock and injection cases; record expected compatible set and clarification outcome; run deterministic suite without API calls. Failure cases: No self-reported model confidence as accuracy; evaluation fixture disjoint from examples used in prompts; failures keep actual output.

## FILES TO MODIFY
No existing runtime file requires modification beyond the documentation updates and package manifests named here.

## HOW IT CONNECTS
Owner: Quality; ARCHITECTURE.md section2. FLOW.md row `21` identifies the entry contract and preceding owners. Required predecessors: F48. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `tests/acceptance/test_f62.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `tests/foundations/test_21.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `F62`: No self-reported model confidence as accuracy; evaluation fixture disjoint from examples used in prompts; failures keep actual output. Assert include four demos plus arabic,typo,serial-boundary,ambiguity,stock and injection cases.

`python tools/run_checks.py --prompt 21` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for labelled evaluations using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `21`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-21` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(quality): 21 labelled evaluations`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
