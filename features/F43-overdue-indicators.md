# F43 - Overdue indicators

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/gateway |
| Implementing prompts | F43; foundations 20 |
| Affected flows | FLOW.md row F43 |

## Scope
Set due_at using configurable urgent/normal thresholds; display overdue only for unresolved states; sort overdue first when requested; store all times UTC.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Set due_at using configurable urgent/normal thresholds; display overdue only for unresolved states; sort overdue first when requested; store all times UTC.
- [ ] Approved/rejected items never overdue; daylight-saving display does not change deadline; thresholds not described as contractual SLA.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
enquiries. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/gateway/tests/features/test_f43.py`; command `python tools/run_checks.py --feature F43`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | F43 | classify_deadline + sort_overdue_first + GET /v1/staff/enquiries/{id}/deadline + web OverdueBadge/lib | committed on prompt/12-deterministic-verification |

## Verification evidence
Application implemented: gateway suite 115 passed incl. services/gateway/tests/features/test_f43.py (11 cases). ruff clean; apps/web vitest 29. Live enquiries adapter BLOCKED.
