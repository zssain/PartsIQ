# F19 - Enquiry history

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/gateway |
| Implementing prompts | F19; foundations 07, 08, 19 |
| Affected flows | FLOW.md row F19 |

## Scope
Return cursor-paginated owned history with status and created time; filter active demo generation; link to full conversation; use stable created_at/id ordering.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Return cursor-paginated owned history with status and created time; filter active demo generation; link to full conversation; use stable created_at/id ordering.
- [ ] Foreign owner ID ignored; invalid cursor returns 422; equal timestamps do not duplicate or skip records.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
enquiries. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/gateway/tests/features/test_f19.py`; command `python tools/run_checks.py --feature F19`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | F19 | list_history keyset pagination + GET /v1/enquiries + web HistoryList/history page | committed on prompt/12-deterministic-verification |

## Verification evidence
Application implemented: gateway suite 44 passed incl. services/gateway/tests/features/test_f19.py (8 cases: newest-first, foreign-owner-ignored, equal-timestamp no dup/skip, status filter, invalid cursor 422, invalid limit 422, cursor roundtrip, dependency failure). ruff clean; apps/web vitest 20 passed. Live enquiries adapter + RLS BLOCKED.
