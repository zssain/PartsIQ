# F53 - Graceful failures (covered by 22)
PHASE: Coverage verification   DEPENDS ON: 22   RISK: low

## GOAL
Verify F53 coverage without implementing it twice. Map stable error codes to bilingual recovery guidance; distinguish validation,quota,service outage and staff-required states; preserve user input.

## READ FIRST
- prompts/22-security-and-failure-recovery-gate.md
- features/F53-graceful-failures.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 22 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 19, 20, 22 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `apps/web/tests/features/f53.test.tsx` is created by 22.

## FILES TO MODIFY
`features/F53-graceful-failures.md`: record actual verification results only.

## HOW IT CONNECTS
Owner apps/web; FLOW rows 19, 20, 22. Covered by 22. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. No raw stack traces or keys; retry only safe idempotent action; search lexical fallback clearly reported.

## ACCEPTANCE TESTS
`apps/web/tests/features/f53.test.tsx` must assert: Map stable error codes to bilingual recovery guidance; distinguish validation,quota,service outage and staff-required states; preserve user input. Negative cases: No raw stack traces or keys; retry only safe idempotent action; search lexical fallback clearly reported.

Run `python tools/run_checks.py --feature F53`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise graceful failures using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F53-graceful-failures.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 22 with a separate trace.

## COMMIT
`docs(features): verify F53 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
