# F54 - Access and permissions (covered by 22)
PHASE: Coverage verification   DEPENDS ON: 22   RISK: low

## GOAL
Verify F54 coverage without implementing it twice. Verify Supabase issuer,audience,signature,expiry; derive identity server-side; enforce assigned-only review; keep credentials server-side; disable public real-client signup.

## READ FIRST
- prompts/22-security-and-failure-recovery-gate.md
- features/F54-access-and-permissions.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 22 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 07, 18, 22 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `services/gateway/tests/features/test_f54.py` is created by 22.

## FILES TO MODIFY
`features/F54-access-and-permissions.md`: record actual verification results only.

## HOW IT CONNECTS
Owner services/gateway; FLOW rows 07, 18, 22. Covered by 22. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. Forged role claim ignored; missing context denies rows; preview cannot reach prod database; demo cannot publish shared catalogue.

## ACCEPTANCE TESTS
`services/gateway/tests/features/test_f54.py` must assert: Verify Supabase issuer,audience,signature,expiry; derive identity server-side; enforce assigned-only review; keep credentials server-side; disable public real-client signup. Negative cases: Forged role claim ignored; missing context denies rows; preview cannot reach prod database; demo cannot publish shared catalogue.

Run `python tools/run_checks.py --feature F54`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise access and permissions using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F54-access-and-permissions.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 22 with a separate trace.

## COMMIT
`docs(features): verify F54 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
