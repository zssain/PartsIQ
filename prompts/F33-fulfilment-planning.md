# F33 - Fulfilment planning (covered by 06)
PHASE: Coverage verification   DEPENDS ON: 06   RISK: low

## GOAL
Verify F33 coverage without implementing it twice. Allocate local stock first then reachable warehouses deterministically; compute shortage; use quantity units; do not reserve stock or create orders.

## READ FIRST
- prompts/06-extend-legacy-search.md
- features/F33-fulfilment-planning.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 06 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 06 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `services/search/tests/features/test_f33.py` is created by 06.

## FILES TO MODIFY
`features/F33-fulfilment-planning.md`: record actual verification results only.

## HOW IT CONNECTS
Owner services/search; FLOW rows 06. Covered by 06. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. Total allocations never exceed request or stock; fractional quantities respect unit policy; unavailable transfer route cannot be invented.

## ACCEPTANCE TESTS
`services/search/tests/features/test_f33.py` must assert: Allocate local stock first then reachable warehouses deterministically; compute shortage; use quantity units; do not reserve stock or create orders. Negative cases: Total allocations never exceed request or stock; fractional quantities respect unit policy; unavailable transfer route cannot be invented.

Run `python tools/run_checks.py --feature F33`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise fulfilment planning using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F33-fulfilment-planning.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 06 with a separate trace.

## COMMIT
`docs(features): verify F33 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
