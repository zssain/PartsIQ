# F53 - Graceful failures

| Field | Value |
|---|---|
| Status | planned |
| Owner module(s) | apps/web |
| Implementing prompts | 22; foundations 19, 20, 22 |
| Affected flows | FLOW.md row 22 |

## Scope
Map stable error codes to bilingual recovery guidance; distinguish validation,quota,service outage and staff-required states; preserve user input.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Map stable error codes to bilingual recovery guidance; distinguish validation,quota,service outage and staff-required states; preserve user input.
- [ ] No raw stack traces or keys; retry only safe idempotent action; search lexical fallback clearly reported.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
jobs, enquiries. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`apps/web/tests/features/f53.test.tsx`; command `python tools/run_checks.py --feature F53`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |

## Verification evidence
Build-kit coverage verified by tools/kit/verify_kit.py. Application tests have not run because this deliverable is an implementation kit. Do not report this feature as implemented until its owning prompt executes.
