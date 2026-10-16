# F09 - Bilingual chat (covered by 19)
PHASE: Coverage verification   DEPENDS ON: 19   RISK: low

## GOAL
Verify F09 coverage without implementing it twice. Accept Arabic, English and mixed text; preserve original message; detect preferred reply locale; render customer messages immediately after successful persistence.

## READ FIRST
- prompts/19-customer-chat-and-demo.md
- features/F09-bilingual-chat.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 19 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 10, 19 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `services/orchestrator/tests/features/test_f09.py` is created by 19.

## FILES TO MODIFY
`features/F09-bilingual-chat.md`: record actual verification results only.

## HOW IT CONNECTS
Owner services/orchestrator; FLOW rows 10, 19. Covered by 19. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. Empty and oversized input returns validation error; HTML is escaped; retry does not duplicate a message.

## ACCEPTANCE TESTS
`services/orchestrator/tests/features/test_f09.py` must assert: Accept Arabic, English and mixed text; preserve original message; detect preferred reply locale; render customer messages immediately after successful persistence. Negative cases: Empty and oversized input returns validation error; HTML is escaped; retry does not duplicate a message.

Run `python tools/run_checks.py --feature F09`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise bilingual chat using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F09-bilingual-chat.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 19 with a separate trace.

## COMMIT
`docs(features): verify F09 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
