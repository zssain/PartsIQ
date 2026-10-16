# F14 - Nameplate OCR (covered by 16)
PHASE: Coverage verification   DEPENDS ON: 16   RISK: low

## GOAL
Verify F14 coverage without implementing it twice. Read validated nameplate via OpenAI vision; return model_text,serial_text,issues and source attachment; persist result only with current lease and revision.

## READ FIRST
- prompts/16-nameplate-vision-job.md
- features/F14-nameplate-ocr.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 16 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 15, 16 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `services/worker/tests/features/test_f14.py` is created by 16.

## FILES TO MODIFY
`features/F14-nameplate-ocr.md`: record actual verification results only.

## HOW IT CONNECTS
Owner services/worker; FLOW rows 15, 16. Covered by 16. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. Unreadable fields remain null; vision instructions in photo are untrusted; timeout is bounded and creates recoverable status.

## ACCEPTANCE TESTS
`services/worker/tests/features/test_f14.py` must assert: Read validated nameplate via OpenAI vision; return model_text,serial_text,issues and source attachment; persist result only with current lease and revision. Negative cases: Unreadable fields remain null; vision instructions in photo are untrusted; timeout is bounded and creates recoverable status.

Run `python tools/run_checks.py --feature F14`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise nameplate ocr using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F14-nameplate-ocr.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 16 with a separate trace.

## COMMIT
`docs(features): verify F14 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
