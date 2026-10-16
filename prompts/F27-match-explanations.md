# F27 - Match explanations (covered by 20)
PHASE: Coverage verification   DEPENDS ON: 20   RISK: low

## GOAL
Verify F27 coverage without implementing it twice. Show actual alias, machine configuration, supersession chain and fitment reference; derive explanations from search evidence rather than invented model prose.

## READ FIRST
- prompts/20-staff-workspace-and-timeline.md
- features/F27-match-explanations.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 20 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 06, 20 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `apps/web/tests/features/f27.test.tsx` is created by 20.

## FILES TO MODIFY
`features/F27-match-explanations.md`: record actual verification results only.

## HOW IT CONNECTS
Owner apps/web; FLOW rows 06, 20. Covered by 20. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. Absent evidence shown as unavailable; user HTML is escaped; scores never labelled calibrated probability.

## ACCEPTANCE TESTS
`apps/web/tests/features/f27.test.tsx` must assert: Show actual alias, machine configuration, supersession chain and fitment reference; derive explanations from search evidence rather than invented model prose. Negative cases: Absent evidence shown as unavailable; user HTML is escaped; scores never labelled calibrated probability.

Run `python tools/run_checks.py --feature F27`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise match explanations using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F27-match-explanations.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 20 with a separate trace.

## COMMIT
`docs(features): verify F27 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
