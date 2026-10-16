# F02 - Demo scenarios and assets (covered by 19)
PHASE: Coverage verification   DEPENDS ON: 19   RISK: low

## GOAL
Verify F02 coverage without implementing it twice. Seed four deterministic scenarios: mixed-language photo, missing serial, incompatible part, local shortage; derive identifiers from seed 42; validate expected outcomes against generated records.

## READ FIRST
- prompts/19-customer-chat-and-demo.md
- features/F02-demo-scenarios-and-assets.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 19 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 05, 19 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `tests/acceptance/test_f02.py` is created by 19.

## FILES TO MODIFY
`features/F02-demo-scenarios-and-assets.md`: record actual verification results only.

## HOW IT CONNECTS
Owner tools/catalog; FLOW rows 05, 19. Covered by 19. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. Reject a scenario whose expected part lacks compatibility; reject stock claims not supported by fixture quantities.

## ACCEPTANCE TESTS
`tests/acceptance/test_f02.py` must assert: Seed four deterministic scenarios: mixed-language photo, missing serial, incompatible part, local shortage; derive identifiers from seed 42; validate expected outcomes against generated records. Negative cases: Reject a scenario whose expected part lacks compatibility; reject stock claims not supported by fixture quantities.

Run `python tools/run_checks.py --feature F02`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise demo scenarios and assets using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F02-demo-scenarios-and-assets.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 19 with a separate trace.

## COMMIT
`docs(features): verify F02 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
