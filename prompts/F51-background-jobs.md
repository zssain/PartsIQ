# F51 - Background jobs (covered by 15)
PHASE: Coverage verification   DEPENDS ON: 15   RISK: low

## GOAL
Verify F51 coverage without implementing it twice. Persist job before Redis dispatch; dispatcher claims by ID; sweeper redispatches pending/expired jobs; worker handles OCR,PDF,imports and cleanup.

## READ FIRST
- prompts/15-worker-leases-and-sweeper.md
- features/F51-background-jobs.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 15 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 15 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `services/worker/tests/features/test_f51.py` is created by 15.

## FILES TO MODIFY
`features/F51-background-jobs.md`: record actual verification results only.

## HOW IT CONNECTS
Owner services/worker; FLOW rows 15. Covered by 15. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. Redis loss does not lose DB job; unavailable Redis rate limiter fails closed; heavy work never blocks HTTP intake.

## ACCEPTANCE TESTS
`services/worker/tests/features/test_f51.py` must assert: Persist job before Redis dispatch; dispatcher claims by ID; sweeper redispatches pending/expired jobs; worker handles OCR,PDF,imports and cleanup. Negative cases: Redis loss does not lose DB job; unavailable Redis rate limiter fails closed; heavy work never blocks HTTP intake.

Run `python tools/run_checks.py --feature F51`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise background jobs using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F51-background-jobs.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 15 with a separate trace.

## COMMIT
`docs(features): verify F51 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
