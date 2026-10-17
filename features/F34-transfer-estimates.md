# F34 - Transfer estimates

| Field | Value |
|---|---|
| Status | done |
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
| 2026-10-17 | 06 | implemented by prompt 06 (prior session); trace flipped to done after re-running its test | committed on prompt/12-deterministic-verification |
| 2026-10-17 | 06 | integer transfer_days from approved route; local==0; no route -> unavailable not invented. test_f34.py. Live DB/BGE-M3 BLOCKED. | prompt/06 |

## Verification evidence
Application implemented by prompt 06; its acceptance test services/search/tests/features/test_f34.py re-verified passing in the owning service suite this session (search 88 / orchestrator 87+1skip / gateway 141 overall). ruff clean. Live infrastructure for the owning service remains BLOCKED and offline-faked per that prompt's notes.
