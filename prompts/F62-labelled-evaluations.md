# F62 - Labelled evaluations (covered by 21)
PHASE: Coverage verification   DEPENDS ON: 21   RISK: low

## GOAL
Verify F62 coverage without implementing it twice. Include four demos plus Arabic,typo,serial-boundary,ambiguity,stock and injection cases; record expected compatible set and clarification outcome; run deterministic suite without API calls.

## READ FIRST
- prompts/21-labelled-evaluations.md
- features/F62-labelled-evaluations.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 21 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 21 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `tests/acceptance/test_f62.py` is created by 21.

## FILES TO MODIFY
`features/F62-labelled-evaluations.md`: record actual verification results only.

## HOW IT CONNECTS
Owner tools/evals; FLOW rows 21. Covered by 21. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. No self-reported model confidence as accuracy; evaluation fixture disjoint from examples used in prompts; failures keep actual output.

## ACCEPTANCE TESTS
`tests/acceptance/test_f62.py` must assert: Include four demos plus Arabic,typo,serial-boundary,ambiguity,stock and injection cases; record expected compatible set and clarification outcome; run deterministic suite without API calls. Negative cases: No self-reported model confidence as accuracy; evaluation fixture disjoint from examples used in prompts; failures keep actual output.

Run `python tools/run_checks.py --feature F62`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise labelled evaluations using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F62-labelled-evaluations.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 21 with a separate trace.

## COMMIT
`docs(features): verify F62 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
