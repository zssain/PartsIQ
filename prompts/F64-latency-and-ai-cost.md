# F64 - Latency and AI cost (covered by 23)
PHASE: Coverage verification   DEPENDS ON: 23   RISK: low

## GOAL
Verify F64 coverage without implementing it twice. Measure stages with monotonic clock; log model/token usage and estimated cost; reserve confirmed free credit before each attempt; expose consumed/reserved allowance.

## READ FIRST
- prompts/23-observability-and-credit-limits.md
- features/F64-latency-and-ai-cost.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 23 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 01, 23 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `tests/acceptance/test_f64.py` is created by 23.

## FILES TO MODIFY
`features/F64-latency-and-ai-cost.md`: record actual verification results only.

## HOW IT CONNECTS
Owner libs/partsiq_common; FLOW rows 01, 23. Covered by 23. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. Unknown price or expired credit blocks calls; concurrent reservations cannot exceed cap; API key validity never implies free credit.

## ACCEPTANCE TESTS
`tests/acceptance/test_f64.py` must assert: Measure stages with monotonic clock; log model/token usage and estimated cost; reserve confirmed free credit before each attempt; expose consumed/reserved allowance. Negative cases: Unknown price or expired credit blocks calls; concurrent reservations cannot exceed cap; API key validity never implies free credit.

Run `python tools/run_checks.py --feature F64`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise latency and ai cost using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F64-latency-and-ai-cost.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 23 with a separate trace.

## COMMIT
`docs(features): verify F64 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
