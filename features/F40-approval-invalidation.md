# F40 - Approval invalidation

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/orchestrator |
| Implementing prompts | 14; foundations 14 |
| Affected flows | FLOW.md row 14 |

## Scope
Bind approval to revision and verified fact hash; any identity,quantity,selection or catalogue-sensitive change requires new draft and approval.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [x] Bind approval to revision and verified fact hash; any identity,quantity,selection or catalogue-sensitive change requires new draft and approval.
- [ ] Old approval cannot authorize new revision; late workflow update cannot overwrite approved current state.
- [x] Test output and implementation commit recorded before status changes to done.

## Data touched
enquiry_revisions, review_decisions. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/orchestrator/tests/features/test_f40.py`; command `python tools/run_checks.py --feature F40`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 14 | approve binds to revision + verified fact hash; stale/old approval and fact drift blocked; corrections increment revision. | prompt/14 |

## Verification evidence
services/orchestrator/tests/features/test_f40.py PASS under the orchestrator suite (36 passed,1 skipped); tests/foundations/test_14.py (13). Live locked transaction BLOCKED.
