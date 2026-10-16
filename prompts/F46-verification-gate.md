# F46 - Verification gate (covered by 12)
PHASE: Coverage verification   DEPENDS ON: 12   RISK: low

## GOAL
Verify F46 coverage without implementing it twice. Check item/configuration/candidate membership, provenance, catalogue version, selected quantities and allocation bounds; compute canonical fact hash; store named rule results.

## READ FIRST
- prompts/12-deterministic-verification.md
- features/F46-verification-gate.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 12 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 12 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `services/orchestrator/tests/features/test_f46.py` is created by 12.

## FILES TO MODIFY
`features/F46-verification-gate.md`: record actual verification results only.

## HOW IT CONNECTS
Owner services/orchestrator; FLOW rows 12. Covered by 12. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. Unknown part, incompatible part, stale catalogue, oversold plan and hidden extra item each fail a specific rule.

## ACCEPTANCE TESTS
`services/orchestrator/tests/features/test_f46.py` must assert: Check item/configuration/candidate membership, provenance, catalogue version, selected quantities and allocation bounds; compute canonical fact hash; store named rule results. Negative cases: Unknown part, incompatible part, stale catalogue, oversold plan and hidden extra item each fail a specific rule.

Run `python tools/run_checks.py --feature F46`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise verification gate using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F46-verification-gate.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 12 with a separate trace.

## COMMIT
`docs(features): verify F46 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
