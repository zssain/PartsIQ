# F05 - Demo reset

| Field | Value |
|---|---|
| Status | planned |
| Owner module(s) | services/gateway |
| Implementing prompts | 19; foundations 07, 15, 19 |
| Affected flows | FLOW.md row 19 |

## Scope
Lock session; increment generation; cancel unfinished jobs from prior generation; enqueue Storage cleanup; keep minimal audit; create fresh scenario enquiries on explicit selection.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Lock session; increment generation; cancel unfinished jobs from prior generation; enqueue Storage cleanup; keep minimal audit; create fresh scenario enquiries on explicit selection.
- [ ] Late OCR from old generation cannot update current data; repeated reset idempotency key returns the same generation.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
demo_sessions, jobs. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/gateway/tests/features/test_f05.py`; command `python tools/run_checks.py --feature F05`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 07 | reset idempotent per key returns same generation; generation increment under row lock (repo); rate limit before DB. test_07.py. Live Supabase Auth + DB BLOCKED. | prompt/07 |

## Verification evidence
Build-kit coverage verified by tools/kit/verify_kit.py. Application tests have not run because this deliverable is an implementation kit. Do not report this feature as implemented until its owning prompt executes.
