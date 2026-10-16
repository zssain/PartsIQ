# F18 - Progress timeline

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | apps/web |
| Implementing prompts | 20; foundations 09, 19, 20 |
| Affected flows | FLOW.md row 20 |

## Scope
Show persisted stages, wait reason and last update; poll with bounded backoff; reconnect using server state; separate waiting for customer from waiting for staff.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [x] Show persisted stages, wait reason and last update; poll with bounded backoff; reconnect using server state; separate waiting for customer from waiting for staff.
- [ ] No fake completed progress; failed poll retains last state and offers retry; hidden tabs reduce polling.
- [x] Test output and implementation commit recorded before status changes to done.

## Data touched
workflow_events, jobs. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`apps/web/tests/features/f18.test.tsx`; command `python tools/run_checks.py --feature F18`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 20 | Timeline renders persisted stages only, separates customer vs staff wait, retries a failed poll; no fabricated completion. | prompt/20 |
| 2026-10-17 | 19 | Progress.tsx: persisted stages, customer-vs-staff wait, retry, no fabricated completion. UI test f18.test.tsx owned by prompt 20. | prompt/19 |
| 2026-10-17 | 09 | controller exposes deterministic stages/wait reasons (await_ocr/confirm/clarify/review as interrupts); no fake completed progress. test_09.py (controller). | prompt/09 |

## Verification evidence
apps/web/tests/features/f18.test.tsx PASS (vitest); Chat polling (prompt 19) covered by test_19.
