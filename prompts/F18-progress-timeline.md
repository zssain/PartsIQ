# F18 - Progress timeline (covered by 20)
PHASE: Coverage verification   DEPENDS ON: 20   RISK: low

## GOAL
Verify F18 coverage without implementing it twice. Show persisted stages, wait reason and last update; poll with bounded backoff; reconnect using server state; separate waiting for customer from waiting for staff.

## READ FIRST
- prompts/20-staff-workspace-and-timeline.md
- features/F18-progress-timeline.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 20 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 09, 19, 20 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `apps/web/tests/features/f18.test.tsx` is created by 20.

## FILES TO MODIFY
`features/F18-progress-timeline.md`: record actual verification results only.

## HOW IT CONNECTS
Owner apps/web; FLOW rows 09, 19, 20. Covered by 20. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. No fake completed progress; failed poll retains last state and offers retry; hidden tabs reduce polling.

## ACCEPTANCE TESTS
`apps/web/tests/features/f18.test.tsx` must assert: Show persisted stages, wait reason and last update; poll with bounded backoff; reconnect using server state; separate waiting for customer from waiting for staff. Negative cases: No fake completed progress; failed poll retains last state and offers retry; hidden tabs reduce polling.

Run `python tools/run_checks.py --feature F18`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise progress timeline using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F18-progress-timeline.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 20 with a separate trace.

## COMMIT
`docs(features): verify F18 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
