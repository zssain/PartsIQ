# F17 - Multi-part enquiries

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/orchestrator |
| Implementing prompts | F17; foundations 09, 10, 11, 12, 13, 14, 19, 20 |
| Affected flows | FLOW.md row F17 |

## Scope
Track up to 20 items with independent quantity, machine, candidate selection and status; clarify individual items; verify aggregate allocation for repeated part requests.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Track up to 20 items with independent quantity, machine, candidate selection and status; clarify individual items; verify aggregate allocation for repeated part requests.
- [ ] One unresolved item blocks final all-items approval; allocations across duplicate parts cannot double count available stock; zero quantity rejected.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
enquiry_items, fulfilment_plans. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/orchestrator/tests/features/test_f17.py`; command `python tools/run_checks.py --feature F17`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | F17 | resolve_items planner + /internal route + handlers readiness rule + web ItemList/lib | committed on prompt/12-deterministic-verification |

## Verification evidence
Application implemented: orchestrator suite 59 passed + 1 skip incl. services/orchestrator/tests/features/test_f17.py (12 cases: success, duplicate-part no-double-count, unresolved blocks approval, needs_information, zero-quantity 422, >20 rejected, exactly-20 tracked, unauthorized 404, demo-session mismatch 404, stale 409, dependency failure, shared readiness rule). ruff clean; apps/web vitest 20 passed. Live DB adapter/RLS and the gateway proxy route remain BLOCKED.
