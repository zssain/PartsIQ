# F12 - Conversation memory (covered by 09)
PHASE: Coverage verification   DEPENDS ON: 09   RISK: low

## GOAL
Verify F12 coverage without implementing it twice. Persist all messages and typed current state; compact context using retained structured facts; resume by enquiry/revision; never mix customer sessions.

## READ FIRST
- prompts/09-deterministic-durable-workflow.md
- features/F12-conversation-memory.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 09 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 03, 09 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `services/orchestrator/tests/features/test_f12.py` is created by 09.

## FILES TO MODIFY
`features/F12-conversation-memory.md`: record actual verification results only.

## HOW IT CONNECTS
Owner services/orchestrator; FLOW rows 03, 09. Covered by 09. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. Restart retains unresolved questions; old revision events are ignored and audited; foreign thread ID denied.

## ACCEPTANCE TESTS
`services/orchestrator/tests/features/test_f12.py` must assert: Persist all messages and typed current state; compact context using retained structured facts; resume by enquiry/revision; never mix customer sessions. Negative cases: Restart retains unresolved questions; old revision events are ignored and audited; foreign thread ID denied.

Run `python tools/run_checks.py --feature F12`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise conversation memory using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F12-conversation-memory.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 09 with a separate trace.

## COMMIT
`docs(features): verify F12 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
