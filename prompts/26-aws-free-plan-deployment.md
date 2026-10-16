# 26 - AWS free-plan deployment
PHASE: Infrastructure   DEPENDS ON: 25   RISK: high

## GOAL
Operator verifies account free-plan eligibility,remaining credits,expiry and region service availability before provisioning. No automatic paid upgrade. Default region ap-south-1 is an operational proposal selected for user proximity; verify account availability before use. Choose instance only after measured CPU/RAM of BGE-M3 and Chromium; free micro capacity is not assumed adequate. Use SSM without public SSH,encrypted volume and minimal IAM. Domain is operator input or no-cost DNS name; HTTPS required. Deploy by immutable release SHA with lock,healthcheck and rollback to previous images.

## READ FIRST
- AGENTS.md
- docs/HANDOVER.md
- docs/CONSTRAINTS.md
- docs/ARCHITECTURE.md sections 2 and 4
- docs/TECH_SPEC.md
- docs/CONTRACTS.md
- docs/FLOW.md
- spec/file-ownership.json


## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
No new package. Use the existing exact pins and committed locks; do not install a second library for this feature.

## FILES TO CREATE
- `infra/ec2/bootstrap.sh`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `infra/ec2/deploy.sh`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `infra/ec2/rollback.sh`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `infra/ec2/preflight.py`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `tests/foundations/test_26.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.

Typed entry contracts:

def preflight(account: AccountReceipt, sizing: SizingReceipt) -> DeploymentDecision; bootstrap.sh accepts a validated environment file path; deploy.sh accepts one hexadecimal release SHA.

Implementation sequence:
1. Operator verifies account free-plan eligibility,remaining credits,expiry and region service availability before provisioning.
2. No automatic paid upgrade.
3. Default region ap-south-1 is an operational proposal selected for user proximity; verify account availability before use.
4. Choose instance only after measured CPU/RAM of BGE-M3 and Chromium; free micro capacity is not assumed adequate.
5. Use SSM without public SSH,encrypted volume and minimal IAM.
6. Domain is operator input or no-cost DNS name; HTTPS required.
7. Deploy by immutable release SHA with lock,healthcheck and rollback to previous images.

## FILES TO MODIFY
- `.github/workflows/deploy-backend.yml`: connect the new implementation through the existing owner; preserve callers and add regression coverage.

## HOW IT CONNECTS
Owner: Infrastructure; ARCHITECTURE.md section2. FLOW.md row `26` identifies the entry contract and preceding owners. Required predecessors: 25. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `tests/foundations/test_26.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.

`python tools/run_checks.py --prompt 26` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for aws free-plan deployment using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `26`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-26` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(infrastructure): 26 aws free-plan deployment`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
