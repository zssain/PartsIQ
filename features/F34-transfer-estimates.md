# F34 - Transfer estimates

| Field | Value |
|---|---|
| Status | planned |
| Owner module(s) | services/search |
| Implementing prompts | 06; foundations 06 |
| Affected flows | FLOW.md row 06 |

## Scope
Carry integer transfer_days from approved route; show estimate and source warehouse; local availability means zero transfer days.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Carry integer transfer_days from approved route; show estimate and source warehouse; local availability means zero transfer days.
- [ ] No route gives unknown/unavailable plan rather than invented one-day promise; estimate labelled non-guaranteed.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
warehouse_transfer_routes. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/search/tests/features/test_f34.py`; command `python tools/run_checks.py --feature F34`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 06 | integer transfer_days from approved route; local==0; no route -> unavailable not invented. test_f34.py. Live DB/BGE-M3 BLOCKED. | prompt/06 |

## Verification evidence
Build-kit coverage verified by tools/kit/verify_kit.py. Application tests have not run because this deliverable is an implementation kit. Do not report this feature as implemented until its owning prompt executes.
