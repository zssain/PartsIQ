# F11 - Clarifying questions (covered by 19)
PHASE: Coverage verification   DEPENDS ON: 19   RISK: low

## GOAL
Verify F11 coverage without implementing it twice. Use controller reason codes to choose code-owned bilingual questions; persist interrupt; associate answer with item; rerun affected resolution only.

## READ FIRST
- prompts/19-customer-chat-and-demo.md
- features/F11-clarifying-questions.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 19 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 09, 11, 19 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `services/orchestrator/tests/features/test_f11.py` is created by 19.

## FILES TO MODIFY
`features/F11-clarifying-questions.md`: record actual verification results only.

## HOW IT CONNECTS
Owner services/orchestrator; FLOW rows 09, 11, 19. Covered by 19. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. No final recommendation before approval; contradictory answer requires confirmation; repeat event creates one question.

## ACCEPTANCE TESTS
`services/orchestrator/tests/features/test_f11.py` must assert: Use controller reason codes to choose code-owned bilingual questions; persist interrupt; associate answer with item; rerun affected resolution only. Negative cases: No final recommendation before approval; contradictory answer requires confirmation; repeat event creates one question.

Run `python tools/run_checks.py --feature F11`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise clarifying questions using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F11-clarifying-questions.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 19 with a separate trace.

## COMMIT
`docs(features): verify F11 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
