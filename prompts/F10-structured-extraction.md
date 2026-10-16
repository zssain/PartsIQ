# F10 - Structured extraction (covered by 10)
PHASE: Coverage verification   DEPENDS ON: 10   RISK: low

## GOAL
Verify F10 coverage without implementing it twice. Extract item descriptions, quantities, urgency and machine hints with strict structured outputs; preserve source spans; missing quantity becomes a clarification rather than assumed order quantity.

## READ FIRST
- prompts/10-intake-specialist.md
- features/F10-structured-extraction.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 10 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 09, 10 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `services/orchestrator/tests/features/test_f10.py` is created by 10.

## FILES TO MODIFY
`features/F10-structured-extraction.md`: record actual verification results only.

## HOW IT CONNECTS
Owner services/orchestrator; FLOW rows 09, 10. Covered by 10. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. Unknown keys and invalid quantities reject the response; unsupported model output cannot progress to search.

## ACCEPTANCE TESTS
`services/orchestrator/tests/features/test_f10.py` must assert: Extract item descriptions, quantities, urgency and machine hints with strict structured outputs; preserve source spans; missing quantity becomes a clarification rather than assumed order quantity. Negative cases: Unknown keys and invalid quantities reject the response; unsupported model output cannot progress to search.

Run `python tools/run_checks.py --feature F10`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise structured extraction using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F10-structured-extraction.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 10 with a separate trace.

## COMMIT
`docs(features): verify F10 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
