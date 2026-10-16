# F47 - Human publication gate (covered by 14)
PHASE: Coverage verification   DEPENDS ON: 14   RISK: low

## GOAL
Verify F47 coverage without implementing it twice. Only approval service inserts recommendation messages; lock enquiry and recheck role,revision and verification; unique publication index prevents duplicates.

## READ FIRST
- prompts/14-approval-and-revision-transactions.md
- features/F47-human-publication-gate.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 14 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 14 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `services/orchestrator/tests/features/test_f47.py` is created by 14.

## FILES TO MODIFY
`features/F47-human-publication-gate.md`: record actual verification results only.

## HOW IT CONNECTS
Owner services/orchestrator; FLOW rows 14. Covered by 14. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. No worker/specialist write tool can publish; database rejects recommendation lacking matching approved decision.

## ACCEPTANCE TESTS
`services/orchestrator/tests/features/test_f47.py` must assert: Only approval service inserts recommendation messages; lock enquiry and recheck role,revision and verification; unique publication index prevents duplicates. Negative cases: No worker/specialist write tool can publish; database rejects recommendation lacking matching approved decision.

Run `python tools/run_checks.py --feature F47`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise human publication gate using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F47-human-publication-gate.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 14 with a separate trace.

## COMMIT
`docs(features): verify F47 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
