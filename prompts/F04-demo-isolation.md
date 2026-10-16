# F04 - Demo isolation (covered by 22)
PHASE: Coverage verification   DEPENDS ON: 22   RISK: low

## GOAL
Verify F04 coverage without implementing it twice. Bind each session to verified anonymous Supabase identity; check generation and expiry on every read, write and worker completion; exclude demos from operational metrics by default.

## READ FIRST
- prompts/22-security-and-failure-recovery-gate.md
- features/F04-demo-isolation.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 22 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 03, 07, 22 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `services/gateway/tests/features/test_f04.py` is created by 22.

## FILES TO MODIFY
`features/F04-demo-isolation.md`: record actual verification results only.

## HOW IT CONNECTS
Owner services/gateway; FLOW rows 03, 07, 22. Covered by 22. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. Expired, reset and foreign sessions fail; missing identity context returns no rows.

## ACCEPTANCE TESTS
`services/gateway/tests/features/test_f04.py` must assert: Bind each session to verified anonymous Supabase identity; check generation and expiry on every read, write and worker completion; exclude demos from operational metrics by default. Negative cases: Expired, reset and foreign sessions fail; missing identity context returns no rows.

Run `python tools/run_checks.py --feature F04`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise demo isolation using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F04-demo-isolation.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 22 with a separate trace.

## COMMIT
`docs(features): verify F04 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
