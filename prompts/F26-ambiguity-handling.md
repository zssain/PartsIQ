# F26 - Ambiguity handling (covered by 11)
PHASE: Coverage verification   DEPENDS ON: 11   RISK: low

## GOAL
Verify F26 coverage without implementing it twice. Use tested score and margin thresholds in code; ask customer to distinguish fuel filter versus separator; allow staff to select only verified candidates.

## READ FIRST
- prompts/11-parts-specialist-and-tools.md
- features/F26-ambiguity-handling.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 11 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 06, 11 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `services/orchestrator/tests/features/test_f26.py` is created by 11.

## FILES TO MODIFY
`features/F26-ambiguity-handling.md`: record actual verification results only.

## HOW IT CONNECTS
Owner services/orchestrator; FLOW rows 06, 11. Covered by 11. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. LLM cannot override low confidence; unavailable candidate choice returns 409; thresholds evaluated on labelled cases.

## ACCEPTANCE TESTS
`services/orchestrator/tests/features/test_f26.py` must assert: Use tested score and margin thresholds in code; ask customer to distinguish fuel filter versus separator; allow staff to select only verified candidates. Negative cases: LLM cannot override low confidence; unavailable candidate choice returns 409; thresholds evaluated on labelled cases.

Run `python tools/run_checks.py --feature F26`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise ambiguity handling using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F26-ambiguity-handling.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 11 with a separate trace.

## COMMIT
`docs(features): verify F26 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
