# F66 - Tests and CI (covered by 25)
PHASE: Coverage verification   DEPENDS ON: 25   RISK: low

## GOAL
Verify F66 coverage without implementing it twice. Run service-isolated Python tests,frontend checks,RLS integration and deterministic evals; build images; require explicit environment approval for deployment; pin action SHAs.

## READ FIRST
- prompts/25-ci-and-controlled-deployment.md
- features/F66-tests-and-ci.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 25 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 00, 25 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `tests/acceptance/test_f66.py` is created by 25.

## FILES TO MODIFY
`features/F66-tests-and-ci.md`: record actual verification results only.

## HOW IT CONNECTS
Owner infra; FLOW rows 00, 25. Covered by 25. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. No prod DB in tests; no secret available to untrusted fork jobs; failed gate blocks deployment.

## ACCEPTANCE TESTS
`tests/acceptance/test_f66.py` must assert: Run service-isolated Python tests,frontend checks,RLS integration and deterministic evals; build images; require explicit environment approval for deployment; pin action SHAs. Negative cases: No prod DB in tests; no secret available to untrusted fork jobs; failed gate blocks deployment.

Run `python tools/run_checks.py --feature F66`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise tests and ci using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F66-tests-and-ci.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 25 with a separate trace.

## COMMIT
`docs(features): verify F66 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
