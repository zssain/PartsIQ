# F41 - Internal notes

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/gateway |
| Implementing prompts | F41; foundations 03, 07, 20 |
| Affected flows | FLOW.md row F41 |

## Scope
Append reviewer notes with author and timestamp; show only in staff workspace; prohibit customer/PDF exposure; escape rendered content.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Append reviewer notes with author and timestamp; show only in staff workspace; prohibit customer/PDF exposure; escape rendered content.
- [ ] Empty or over-4000-character note rejected; customer route never includes note text; unassigned staff denied.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
internal_notes. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/gateway/tests/features/test_f41.py`; command `python tools/run_checks.py --feature F41`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | F41 | append_note + list_notes + POST/GET /v1/staff/enquiries/{id}/notes + web InternalNotes/lib | committed on prompt/12-deterministic-verification |

## Verification evidence
Application implemented: gateway suite 105 passed incl. services/gateway/tests/features/test_f41.py (9 cases). ruff clean; apps/web vitest 29. Live notes adapter BLOCKED.
