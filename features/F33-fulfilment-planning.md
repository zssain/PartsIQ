# F33 - Fulfilment planning

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/search |
| Implementing prompts | 06; foundations 06 |
| Affected flows | FLOW.md row 06 |

## Scope
Allocate local stock first then reachable warehouses deterministically; compute shortage; use quantity units; do not reserve stock or create orders.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Allocate local stock first then reachable warehouses deterministically; compute shortage; use quantity units; do not reserve stock or create orders.
- [ ] Total allocations never exceed request or stock; fractional quantities respect unit policy; unavailable transfer route cannot be invented.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
stock_levels, warehouse_transfer_routes. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/search/tests/features/test_f33.py`; command `python tools/run_checks.py --feature F33`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 06 | implemented by prompt 06 (prior session); trace flipped to done after re-running its test | committed on prompt/12-deterministic-verification |
| 2026-10-17 | 06 | local-first then nearest remotes; allocations bounded; invented route rejected; unknown destination rejected. test_f33.py. Live DB/BGE-M3 BLOCKED. | prompt/06 |

## Verification evidence
Application implemented by prompt 06; its acceptance test services/search/tests/features/test_f33.py re-verified passing in the owning service suite this session (search 88 / orchestrator 87+1skip / gateway 141 overall). ruff clean. Live infrastructure for the owning service remains BLOCKED and offline-faked per that prompt's notes.
