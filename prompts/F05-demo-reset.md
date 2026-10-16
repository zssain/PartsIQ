# F05 - Demo reset (covered by 19)
PHASE: Coverage verification   DEPENDS ON: 19   RISK: low

## GOAL
Verify F05 coverage without implementing it twice. Lock session; increment generation; cancel unfinished jobs from prior generation; enqueue Storage cleanup; keep minimal audit; create fresh scenario enquiries on explicit selection.

## READ FIRST
- prompts/19-customer-chat-and-demo.md
- features/F05-demo-reset.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 19 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 07, 15, 19 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `services/gateway/tests/features/test_f05.py` is created by 19.

## FILES TO MODIFY
`features/F05-demo-reset.md`: record actual verification results only.

## HOW IT CONNECTS
Owner services/gateway; FLOW rows 07, 15, 19. Covered by 19. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. Late OCR from old generation cannot update current data; repeated reset idempotency key returns the same generation.

## ACCEPTANCE TESTS
`services/gateway/tests/features/test_f05.py` must assert: Lock session; increment generation; cancel unfinished jobs from prior generation; enqueue Storage cleanup; keep minimal audit; create fresh scenario enquiries on explicit selection. Negative cases: Late OCR from old generation cannot update current data; repeated reset idempotency key returns the same generation.

Run `python tools/run_checks.py --feature F05`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise demo reset using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F05-demo-reset.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 19 with a separate trace.

## COMMIT
`docs(features): verify F05 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
