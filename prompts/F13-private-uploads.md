# F13 - Private uploads (covered by 19)
PHASE: Coverage verification   DEPENDS ON: 19   RISK: low

## GOAL
Verify F13 coverage without implementing it twice. Create pending attachment and unique object path; use signed upload; validate actual bytes and magic type after confirmation; strip EXIF and cap decoded pixels before OCR.

## READ FIRST
- prompts/19-customer-chat-and-demo.md
- features/F13-private-uploads.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 19 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 04, 08, 19 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `services/gateway/tests/features/test_f13.py` is created by 19.

## FILES TO MODIFY
`features/F13-private-uploads.md`: record actual verification results only.

## HOW IT CONNECTS
Owner services/gateway; FLOW rows 04, 08, 19. Covered by 19. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. Wrong MIME, oversized content, image decompression bomb, duplicate confirmation and nonexistent object handled explicitly.

## ACCEPTANCE TESTS
`services/gateway/tests/features/test_f13.py` must assert: Create pending attachment and unique object path; use signed upload; validate actual bytes and magic type after confirmation; strip EXIF and cap decoded pixels before OCR. Negative cases: Wrong MIME, oversized content, image decompression bomb, duplicate confirmation and nonexistent object handled explicitly.

Run `python tools/run_checks.py --feature F13`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise private uploads using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F13-private-uploads.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 19 with a separate trace.

## COMMIT
`docs(features): verify F13 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
