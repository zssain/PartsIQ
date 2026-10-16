# F52 - Retry and deduplication (covered by 15)
PHASE: Coverage verification   DEPENDS ON: 15   RISK: low

## GOAL
Verify F52 coverage without implementing it twice. Claim with FOR UPDATE SKIP LOCKED; assign lease token; heartbeat; retry transient errors with backoff up to max attempts; fence final writes by lease token.

## READ FIRST
- prompts/15-worker-leases-and-sweeper.md
- features/F52-retry-and-deduplication.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 15 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 15 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `services/worker/tests/features/test_f52.py` is created by 15.

## FILES TO MODIFY
`features/F52-retry-and-deduplication.md`: record actual verification results only.

## HOW IT CONNECTS
Owner services/worker; FLOW rows 15. Covered by 15. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. Expired worker cannot commit; permanent validation failure not retried; provider timeout marked uncertain and budget held conservatively.

## ACCEPTANCE TESTS
`services/worker/tests/features/test_f52.py` must assert: Claim with FOR UPDATE SKIP LOCKED; assign lease token; heartbeat; retry transient errors with backoff up to max attempts; fence final writes by lease token. Negative cases: Expired worker cannot commit; permanent validation failure not retried; provider timeout marked uncertain and budget held conservatively.

Run `python tools/run_checks.py --feature F52`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise retry and deduplication using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F52-retry-and-deduplication.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 15 with a separate trace.

## COMMIT
`docs(features): verify F52 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
