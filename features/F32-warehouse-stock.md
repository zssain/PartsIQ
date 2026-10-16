# F32 - Warehouse stock

| Field | Value |
|---|---|
| Status | planned |
| Owner module(s) | services/search |
| Implementing prompts | 20; foundations 06, 20 |
| Affected flows | FLOW.md row 20 |

## Scope
Show available quantity as on_hand minus reserved; include timestamp and warehouse name; keep display and planner using same snapshot.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Show available quantity as on_hand minus reserved; include timestamp and warehouse name; keep display and planner using same snapshot.
- [ ] Negative stock blocked; stock unavailable never displayed as zero without explanation; unknown warehouse rejected.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
stock_levels, warehouses. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/search/tests/features/test_f32.py`; command `python tools/run_checks.py --feature F32`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |

## Verification evidence
Build-kit coverage verified by tools/kit/verify_kit.py. Application tests have not run because this deliverable is an implementation kit. Do not report this feature as implemented until its owning prompt executes.
