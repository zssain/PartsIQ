# F61 - Enquiry PDF (covered by 20)
PHASE: Coverage verification   DEPENDS ON: 20   RISK: low

## GOAL
Verify F61 coverage without implementing it twice. Export approved revision only; render logo,bilingual customer text,verified selections,estimates and references; embed Arabic fonts; store private object and signed download.

## READ FIRST
- prompts/20-staff-workspace-and-timeline.md
- features/F61-enquiry-pdf.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 20 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 17, 20 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `services/worker/tests/features/test_f61.py` is created by 20.

## FILES TO MODIFY
`features/F61-enquiry-pdf.md`: record actual verification results only.

## HOW IT CONNECTS
Owner services/worker; FLOW rows 17, 20. Covered by 20. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. Exclude notes and secrets; stale or unapproved revision rejected; long Arabic names wrap without clipping; no prices or quotation title.

## ACCEPTANCE TESTS
`services/worker/tests/features/test_f61.py` must assert: Export approved revision only; render logo,bilingual customer text,verified selections,estimates and references; embed Arabic fonts; store private object and signed download. Negative cases: Exclude notes and secrets; stale or unapproved revision rejected; long Arabic names wrap without clipping; no prices or quotation title.

Run `python tools/run_checks.py --feature F61`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise enquiry pdf using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F61-enquiry-pdf.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 20 with a separate trace.

## COMMIT
`docs(features): verify F61 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
