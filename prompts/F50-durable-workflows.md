# F50 - Durable workflows (covered by 09)
PHASE: Coverage verification   DEPENDS ON: 09   RISK: low

## GOAL
Verify F50 coverage without implementing it twice. Use Postgres checkpointer and DB event inbox; thread key includes enquiry ID and active revision; serialize processing for one enquiry; recover after restart.

## READ FIRST
- prompts/09-deterministic-durable-workflow.md
- features/F50-durable-workflows.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 09 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 09 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `services/orchestrator/tests/features/test_f50.py` is created by 09.

## FILES TO MODIFY
`features/F50-durable-workflows.md`: record actual verification results only.

## HOW IT CONNECTS
Owner services/orchestrator; FLOW rows 09. Covered by 09. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. Duplicate events do not repeat publication; stale revision event is consumed as obsolete; checkpoint DDL never runs under runtime role.

## ACCEPTANCE TESTS
`services/orchestrator/tests/features/test_f50.py` must assert: Use Postgres checkpointer and DB event inbox; thread key includes enquiry ID and active revision; serialize processing for one enquiry; recover after restart. Negative cases: Duplicate events do not repeat publication; stale revision event is consumed as obsolete; checkpoint DDL never runs under runtime role.

Run `python tools/run_checks.py --feature F50`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise durable workflows using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F50-durable-workflows.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 09 with a separate trace.

## COMMIT
`docs(features): verify F50 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
