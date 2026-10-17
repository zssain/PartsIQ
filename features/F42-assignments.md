# F42 - Assignments

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/gateway |
| Implementing prompts | F42; foundations 03, 07, 20 |
| Affected flows | FLOW.md row F42 |

## Scope
Admin assigns active reviewer or unassigns; persist assignment history atomically; access changes immediately; demo reviewer access remains session-scoped.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Admin assigns active reviewer or unassigns; persist assignment history atomically; access changes immediately; demo reviewer access remains session-scoped.
- [ ] Non-admin assignment denied; disabled/nonreviewer assignee rejected; previous reviewer loses access on next request.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
enquiries, assignment_events. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/gateway/tests/features/test_f42.py`; command `python tools/run_checks.py --feature F42`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | F42 | assign_enquiry admin-only + POST /v1/staff/enquiries/{id}/assignment + web AssignmentControl/lib | committed on prompt/12-deterministic-verification |

## Verification evidence
Application implemented: gateway suite 96 passed incl. services/gateway/tests/features/test_f42.py (9 cases). ruff clean; apps/web vitest 29. Live assignment tx + events BLOCKED.
