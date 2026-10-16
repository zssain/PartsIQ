# F32 - Warehouse stock (covered by 20)
PHASE: Coverage verification   DEPENDS ON: 20   RISK: low

## GOAL
Verify F32 coverage without implementing it twice. Show available quantity as on_hand minus reserved; include timestamp and warehouse name; keep display and planner using same snapshot.

## READ FIRST
- prompts/20-staff-workspace-and-timeline.md
- features/F32-warehouse-stock.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 20 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 06, 20 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `services/search/tests/features/test_f32.py` is created by 20.

## FILES TO MODIFY
`features/F32-warehouse-stock.md`: record actual verification results only.

## HOW IT CONNECTS
Owner services/search; FLOW rows 06, 20. Covered by 20. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. Negative stock blocked; stock unavailable never displayed as zero without explanation; unknown warehouse rejected.

## ACCEPTANCE TESTS
`services/search/tests/features/test_f32.py` must assert: Show available quantity as on_hand minus reserved; include timestamp and warehouse name; keep display and planner using same snapshot. Negative cases: Negative stock blocked; stock unavailable never displayed as zero without explanation; unknown warehouse rejected.

Run `python tools/run_checks.py --feature F32`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise warehouse stock using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F32-warehouse-stock.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 20 with a separate trace.

## COMMIT
`docs(features): verify F32 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
