# F45 - Reply drafting (covered by 13)
PHASE: Coverage verification   DEPENDS ON: 13   RISK: low

## GOAL
Verify F45 coverage without implementing it twice. Generate greeting,explanation and closing as structured slots; code inserts all numbers and allocations; choose Arabic or English from confirmed preference.

## READ FIRST
- prompts/13-reply-specialist-and-renderer.md
- features/F45-reply-drafting.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 13 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 13 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `services/orchestrator/tests/features/test_f45.py` is created by 13.

## FILES TO MODIFY
`features/F45-reply-drafting.md`: record actual verification results only.

## HOW IT CONNECTS
Owner services/orchestrator; FLOW rows 13. Covered by 13. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. Unapproved critical facts never rendered; unsupported slots rejected; provider failure permits staff-authored controlled draft.

## ACCEPTANCE TESTS
`services/orchestrator/tests/features/test_f45.py` must assert: Generate greeting,explanation and closing as structured slots; code inserts all numbers and allocations; choose Arabic or English from confirmed preference. Negative cases: Unapproved critical facts never rendered; unsupported slots rejected; provider failure permits staff-authored controlled draft.

Run `python tools/run_checks.py --feature F45`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise reply drafting using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F45-reply-drafting.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 13 with a separate trace.

## COMMIT
`docs(features): verify F45 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
