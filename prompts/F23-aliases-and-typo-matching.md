# F23 - Aliases and typo matching (covered by 06)
PHASE: Coverage verification   DEPENDS ON: 06   RISK: low

## GOAL
Verify F23 coverage without implementing it twice. Preserve Arabic normalization, part-number keys, phrase scoring and fuzzy token matching; remove machine terms using resolved model context.

## READ FIRST
- prompts/06-extend-legacy-search.md
- features/F23-aliases-and-typo-matching.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 06 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 06 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `services/search/tests/features/test_f23.py` is created by 06.

## FILES TO MODIFY
`features/F23-aliases-and-typo-matching.md`: record actual verification results only.

## HOW IT CONNECTS
Owner services/search; FLOW rows 06. Covered by 06. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. Arabic part words are not removed as machine words; exact part number outranks unrelated fuzzy alias; normalization parity test matches SQL.

## ACCEPTANCE TESTS
`services/search/tests/features/test_f23.py` must assert: Preserve Arabic normalization, part-number keys, phrase scoring and fuzzy token matching; remove machine terms using resolved model context. Negative cases: Arabic part words are not removed as machine words; exact part number outranks unrelated fuzzy alias; normalization parity test matches SQL.

Run `python tools/run_checks.py --feature F23`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise aliases and typo matching using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F23-aliases-and-typo-matching.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 06 with a separate trace.

## COMMIT
`docs(features): verify F23 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
