# F36 - Staff inbox

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/gateway |
| Implementing prompts | F36; foundations 07, 20 |
| Affected flows | FLOW.md row F36 |

## Scope
List assigned operational enquiries and own active demo enquiries; filter status,priority,overdue and text; paginate stably; show counts in same access scope.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] List assigned operational enquiries and own active demo enquiries; filter status,priority,overdue and text; paginate stably; show counts in same access scope.
- [ ] Unassigned real enquiries hidden from reviewer; admin can see all; filters do not leak global counts.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
enquiries. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/gateway/tests/features/test_f36.py`; command `python tools/run_checks.py --feature F36`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | F36 | list_inbox scoped+filtered+paged + GET /v1/staff/enquiries + web InboxFilters/inbox page | committed on prompt/12-deterministic-verification |

## Verification evidence
Application implemented: gateway suite 124 passed incl. services/gateway/tests/features/test_f36.py (9 cases). ruff clean; apps/web vitest 29. Live scope-aware inbox adapter BLOCKED.
