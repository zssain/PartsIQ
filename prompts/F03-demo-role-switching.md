# F03 - Demo role switching (covered by 20)
PHASE: Coverage verification   DEPENDS ON: 20   RISK: low

## GOAL
Verify F03 coverage without implementing it twice. Switch the presentation between customer and reviewer using the same anonymous identity and session; authorize review only for enquiries belonging to that active session.

## READ FIRST
- prompts/20-staff-workspace-and-timeline.md
- features/F03-demo-role-switching.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 20 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 07, 19, 20 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `services/gateway/tests/features/test_f03.py` is created by 20.

## FILES TO MODIFY
`features/F03-demo-role-switching.md`: record actual verification results only.

## HOW IT CONNECTS
Owner services/gateway; FLOW rows 07, 19, 20. Covered by 20. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. Forged reviewer role never grants staff membership; another visitor's enquiry returns 404.

## ACCEPTANCE TESTS
`services/gateway/tests/features/test_f03.py` must assert: Switch the presentation between customer and reviewer using the same anonymous identity and session; authorize review only for enquiries belonging to that active session. Negative cases: Forged reviewer role never grants staff membership; another visitor's enquiry returns 404.

Run `python tools/run_checks.py --feature F03`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise demo role switching using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F03-demo-role-switching.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 20 with a separate trace.

## COMMIT
`docs(features): verify F03 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
