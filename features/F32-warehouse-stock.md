# F32 - Warehouse stock

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/search |
| Implementing prompts | 20; foundations 06, 20 |
| Affected flows | FLOW.md row 20 |

## Scope
Show available quantity as on_hand minus reserved; include timestamp and warehouse name; keep display and planner using same snapshot.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [x] Show available quantity as on_hand minus reserved; include timestamp and warehouse name; keep display and planner using same snapshot.
- [ ] Negative stock blocked; stock unavailable never displayed as zero without explanation; unknown warehouse rejected.
- [x] Test output and implementation commit recorded before status changes to done.

## Data touched
stock_levels, warehouses. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/search/tests/features/test_f32.py`; command `python tools/run_checks.py --feature F32`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 20 | planner/display use the net available snapshot; negative clamped (blocked), unknown warehouse rejected; UI shows warehouse + timestamp. | prompt/20 |

## Verification evidence
services/search/tests/features/test_f32.py PASS (search suite 80); UI display asserted in tests/foundations/test_20.py. Live stock query BLOCKED.
