# F49 - Audit trail (covered by 14)
PHASE: Coverage verification   DEPENDS ON: 14   RISK: low

## GOAL
Verify F49 coverage without implementing it twice. Append actor,request,entity,revision and minimal before/after metadata for AI suggestions and human changes; redact secrets and full sensitive payloads.

## READ FIRST
- prompts/14-approval-and-revision-transactions.md
- features/F49-audit-trail.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 14 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 01, 03, 14 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `tests/acceptance/test_f49.py` is created by 14.

## FILES TO MODIFY
`features/F49-audit-trail.md`: record actual verification results only.

## HOW IT CONNECTS
Owner libs/partsiq_common; FLOW rows 01, 03, 14. Covered by 14. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. Application UPDATE,DELETE,TRUNCATE fail; audit write failure rolls back approval; database-owner powers documented honestly.

## ACCEPTANCE TESTS
`tests/acceptance/test_f49.py` must assert: Append actor,request,entity,revision and minimal before/after metadata for AI suggestions and human changes; redact secrets and full sensitive payloads. Negative cases: Application UPDATE,DELETE,TRUNCATE fail; audit write failure rolls back approval; database-owner powers documented honestly.

Run `python tools/run_checks.py --feature F49`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise audit trail using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F49-audit-trail.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 14 with a separate trace.

## COMMIT
`docs(features): verify F49 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
