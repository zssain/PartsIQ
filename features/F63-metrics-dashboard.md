# F63 - Metrics dashboard

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/gateway |
| Implementing prompts | F63; foundations 21, 23 |
| Affected flows | FLOW.md row F63 |

## Scope
Show volume,status,review time,clarification and labelled accuracy with denominators; separate demo traffic; filter time window; scope reviewer data to assignments.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Show volume,status,review time,clarification and labelled accuracy with denominators; separate demo traffic; filter time window; scope reviewer data to assignments.
- [ ] Zero denominator displays unavailable; no fabricated percentage; demo traffic never silently improves operational metrics.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
eval_runs, eval_results, enquiries. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/gateway/tests/features/test_f63.py`; command `python tools/run_checks.py --feature F63`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | F63 | metrics_dashboard (admin-gated accuracy, denominators, demo-excluded) + GET /v1/staff/analytics + web MetricsDashboard | committed on prompt/12-deterministic-verification |

## Verification evidence
Application implemented: gateway suite 131 passed incl. services/gateway/tests/features/test_f63.py (7 cases). ruff clean; apps/web vitest 44. Live metrics adapter BLOCKED.
