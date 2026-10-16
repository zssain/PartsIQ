# F53 - Graceful failures

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | apps/web |
| Implementing prompts | 22; foundations 19, 20, 22 |
| Affected flows | FLOW.md row 22 |

## Scope
Map stable error codes to bilingual recovery guidance; distinguish validation,quota,service outage and staff-required states; preserve user input.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [x] Map stable error codes to bilingual recovery guidance; distinguish validation,quota,service outage and staff-required states; preserve user input.
- [ ] No raw stack traces or keys; retry only safe idempotent action; search lexical fallback clearly reported.
- [x] Test output and implementation commit recorded before status changes to done.

## Data touched
jobs, enquiries. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`apps/web/tests/features/f53.test.tsx`; command `python tools/run_checks.py --feature F53`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 20 | lib/api typed ApiError + chat/approval map stable codes to safe guidance, preserve input, retry only idempotent actions; 409 forces fresh review. | prompt/20 |
| 2026-10-17 | 19 | chat/api map stable codes to safe guidance, preserve unsent input, retry only idempotent sends. Full matrix owned by 20/22. | prompt/19 |

## Verification evidence
Covered by tests/foundations/test_19.py + test_20.py and apps/web vitest (f37 stale/409). Search lexical-fallback is reported by /readiness (prompt 06).
