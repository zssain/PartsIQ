# F39 - Review actions (covered by 20)
PHASE: Coverage verification   DEPENDS ON: 20   RISK: low

## GOAL
Verify F39 coverage without implementing it twice. Approve only verified current draft; edit prose through controlled schema then reverify; reject with reason; record actor and idempotency key.

## READ FIRST
- prompts/20-staff-workspace-and-timeline.md
- features/F39-review-actions.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 20 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 14, 20 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `services/orchestrator/tests/features/test_f39.py` is created by 20.

## FILES TO MODIFY
`features/F39-review-actions.md`: record actual verification results only.

## HOW IT CONNECTS
Owner services/orchestrator; FLOW rows 14, 20. Covered by 20. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. Double-click publishes once; concurrent edit defeats stale approval; failed verification blocks publication.

## ACCEPTANCE TESTS
`services/orchestrator/tests/features/test_f39.py` must assert: Approve only verified current draft; edit prose through controlled schema then reverify; reject with reason; record actor and idempotency key. Negative cases: Double-click publishes once; concurrent edit defeats stale approval; failed verification blocks publication.

Run `python tools/run_checks.py --feature F39`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise review actions using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F39-review-actions.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 20 with a separate trace.

## COMMIT
`docs(features): verify F39 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
