# F01 - Branded landing (covered by 18)
PHASE: Coverage verification   DEPENDS ON: 18   RISK: low

## GOAL
Verify F01 coverage without implementing it twice. Explain the enquiry-to-approval journey; show synthetic-demo notice; expose Start demo and architecture links; display the supplied bilingual logo without stretching.

## READ FIRST
- prompts/18-frontend-shell-and-authentication.md
- features/F01-branded-landing.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 18 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 18 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `apps/web/tests/features/f01.test.tsx` is created by 18.

## FILES TO MODIFY
`features/F01-branded-landing.md`: record actual verification results only.

## HOW IT CONNECTS
Owner apps/web; FLOW rows 18. Covered by 18. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. Missing repository link hides that action; logo has meaningful alternative text; no affiliation claim.

## ACCEPTANCE TESTS
`apps/web/tests/features/f01.test.tsx` must assert: Explain the enquiry-to-approval journey; show synthetic-demo notice; expose Start demo and architecture links; display the supplied bilingual logo without stretching. Negative cases: Missing repository link hides that action; logo has meaningful alternative text; no affiliation claim.

Run `python tools/run_checks.py --feature F01`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise branded landing using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F01-branded-landing.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 18 with a separate trace.

## COMMIT
`docs(features): verify F01 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
