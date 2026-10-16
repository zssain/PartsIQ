# 00 - Bootstrap and preserve legacy
PHASE: Repository   DEPENDS ON: none   RISK: high

## GOAL
Preserve all files in references/legacy-backend.zip at their original relative paths; retain checksum manifest before modifications. Create one root uv workspace, with named common,gateway,search,orchestrator,worker and catalogue projects. Use a single uv.lock. Run service tests in separate processes because legacy services share the app import name. Local Compose publishes gateway on 127.0.0.1 only and uses local Supabase CLI endpoints. Do not copy real secrets or rewrite domain modules.

## READ FIRST
- AGENTS.md
- docs/HANDOVER.md
- docs/CONSTRAINTS.md
- docs/ARCHITECTURE.md sections 2 and 4
- docs/TECH_SPEC.md
- docs/CONTRACTS.md
- docs/FLOW.md
- spec/file-ownership.json
- features/F66-tests-and-ci.md

## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
- `uv pip install PyYAML==6.0.3 pytest==9.0.2 pytest-asyncio==1.3.0 ruff==0.15.6 mypy==1.19.1` in the task-specific development environment. Add the identical pins to the owning workspace project; synchronize from the shared workspace lock for application execution.
- `python -m pip install uv==0.10.9`

Release dates and registry receipts are in spec/dependency-receipts.json. Use spec/python-requirements.lock and spec/pnpm-lock.yaml as resolution references; do not claim installing these packages proves application compatibility.

## FILES TO CREATE
- `README.md`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `pyproject.toml`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `.gitignore`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `.env.example`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `.python-version`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `.nvmrc`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `docker-compose.yml`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/orchestrator/pyproject.toml`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `services/worker/pyproject.toml`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tools/verify_env.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tools/run_checks.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tools/check_release_eligibility.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `uv.lock`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tests/foundations/test_00.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.

Typed entry contracts:

def verify_environment(env: Mapping[str,str]) -> list[str]: return missing or unsafe environment names without values; reject prod database URLs when APP_ENV is local.

Implementation sequence:
1. Preserve all files in references/legacy-backend.zip at their original relative paths; retain checksum manifest before modifications.
2. Create one root uv workspace, with named common,gateway,search,orchestrator,worker and catalogue projects.
3. Use a single uv.lock.
4. Run service tests in separate processes because legacy services share the app import name.
5. Local Compose publishes gateway on 127.0.0.1 only and uses local Supabase CLI endpoints.
6. Do not copy real secrets or rewrite domain modules.

Required feature behaviours:
- F66 Tests and CI: Run service-isolated Python tests,frontend checks,RLS integration and deterministic evals; build images; require explicit environment approval for deployment; pin action SHAs. Failure cases: No prod DB in tests; no secret available to untrusted fork jobs; failed gate blocks deployment.

Exact package markers and bundled assets created by this step:
- `tools/catalog/__init__.py`

## FILES TO MODIFY
No existing runtime file requires modification beyond the documentation updates and package manifests named here.

## HOW IT CONNECTS
Owner: Repository; ARCHITECTURE.md section2. FLOW.md row `00` identifies the entry contract and preceding owners. Required predecessors: none. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `tests/foundations/test_00.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `F66`: No prod DB in tests; no secret available to untrusted fork jobs; failed gate blocks deployment. Assert run service-isolated python tests,frontend checks,rls integration and deterministic evals.

`python tools/run_checks.py --prompt 00` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for bootstrap and preserve legacy using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `00`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-00` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(repository): 00 bootstrap and preserve legacy`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
