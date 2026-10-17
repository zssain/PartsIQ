# F35 - Stock freshness

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/search |
| Implementing prompts | F35; foundations 06, 12, 14, 20 |
| Affected flows | FLOW.md row F35 |

## Scope
Compare stock timestamp with configurable freshness limit; mark stale data in review; re-read current stock during approval; invalidate plan when allocation no longer possible.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Compare stock timestamp with configurable freshness limit; mark stale data in review; re-read current stock during approval; invalidate plan when allocation no longer possible.
- [ ] Future timestamp flagged; changed stock returns 409 and reruns planning; stale stock never becomes a delivery guarantee.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
stock_levels, fulfilment_plans. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/search/tests/features/test_f35.py`; command `python tools/run_checks.py --feature F35`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | F35 | check_stock_freshness + /internal/stock/check route + approval re-read note + web StockFreshness | committed on prompt/12-deterministic-verification |

## Verification evidence
Application implemented: search suite 88 passed incl. services/search/tests/features/test_f35.py (8 cases). orchestrator 59+1skip; ruff clean; apps/web vitest 20. Live stock reader + approval->search call BLOCKED.
