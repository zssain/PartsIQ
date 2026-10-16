# F67 - Traces (covered by 23)
PHASE: Coverage verification   DEPENDS ON: 23   RISK: low

## GOAL
Verify F67 coverage without implementing it twice. Propagate request/enquiry/job IDs; capture stage timing and safe status; export optional Langfuse traces with payload redaction; operate normally when tracing unavailable.

## READ FIRST
- prompts/23-observability-and-credit-limits.md
- features/F67-traces.md
- docs/CONSTRAINTS.md
- docs/CONTRACTS.md

## PLAN CHECK
Confirm foundation 23 has executed and its acceptance evidence exists. If coverage is incomplete,complete that foundation's named implementation rather than creating a second owner.

## PACKAGES
No installation here. Packages are installed by foundations 01, 09, 23 and recorded in spec/dependency-receipts.json.

## FILES TO CREATE
None. `tests/acceptance/test_f67.py` is created by 23.

## FILES TO MODIFY
`features/F67-traces.md`: record actual verification results only.

## HOW IT CONNECTS
Owner libs/partsiq_common; FLOW rows 01, 09, 23. Covered by 23. Follow existing entry contracts in the foundation prompt.

## CONSTRAINTS FOR THIS STEP
No duplicate domain function,route or state. No raw key or full photo logged; exporter outage never breaks approval; budget accounting remains local and authoritative.

## ACCEPTANCE TESTS
`tests/acceptance/test_f67.py` must assert: Propagate request/enquiry/job IDs; capture stage timing and safe status; export optional Langfuse traces with payload redaction; operate normally when tracing unavailable. Negative cases: No raw key or full photo logged; exporter outage never breaks approval; budget accounting remains local and authoritative.

Run `python tools/run_checks.py --feature F67`. Expected: exit0,all feature assertions pass,no required skips. Record actual test count.

## MANUAL VERIFICATION
Exercise traces using synthetic fixtures. Compare persisted and visible outcomes; inspect its failure cases. Do not mark done from source inspection alone.

## DOC UPDATES
Update features/F67-traces.md,docs/HANDOVER.md and docs/SESSION_LOG.md with foundation owner and verification output.

## ROLLBACK
This coverage check changes documentation only. Revert its documentation commit if wrong; any code defect is fixed under foundation 23 with a separate trace.

## COMMIT
`docs(features): verify F67 foundation coverage`

## DONE WHEN
- [ ] Foundation evidence exists.
- [ ] Feature tests pass.
- [ ] Trace links exact command and commit.
- [ ] No duplicate implementation introduced.
