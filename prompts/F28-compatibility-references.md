# F28 - Compatibility references (covered by 12)
PHASE: Coverage verification   DEPENDS ON: 12   RISK: low

## GOAL
Verify F28 coverage without implementing it twice. Resolve source_reference to version-specific document and page; retain citation with every candidate and approval snapshot.

## READ FIRST
- prompts/12-deterministic-verification.md
- features/F28-compatibility-references.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 12 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 02, 06, 12 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `services/search/tests/features/test_f28.py` is created by 12.

## FILES TO MODIFY
`features/F28-compatibility-references.md`: record actual verification results only.

## HOW IT CONNECTS
Owner services/search; FLOW rows 02, 06, 12. Covered by 12. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. Missing source file blocks evidence viewer and flags review; mismatched version fails verification.

## ACCEPTANCE TESTS
`services/search/tests/features/test_f28.py` must assert: Resolve source_reference to version-specific document and page; retain citation with every candidate and approval snapshot. Negative cases: Missing source file blocks evidence viewer and flags review; mismatched version fails verification.

Run `python tools/run_checks.py --feature F28`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise compatibility references using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F28-compatibility-references.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 12 with a separate trace.

## COMMIT
`docs(features): verify F28 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
