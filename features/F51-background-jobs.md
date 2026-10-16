# F51 - Background jobs

| Field | Value |
|---|---|
| Status | planned |
| Owner module(s) | services/worker |
| Implementing prompts | 15; foundations 15 |
| Affected flows | FLOW.md row 15 |

## Scope
Persist job before Redis dispatch; dispatcher claims by ID; sweeper redispatches pending/expired jobs; worker handles OCR,PDF,imports and cleanup.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Persist job before Redis dispatch; dispatcher claims by ID; sweeper redispatches pending/expired jobs; worker handles OCR,PDF,imports and cleanup.
- [ ] Redis loss does not lose DB job; unavailable Redis rate limiter fails closed; heavy work never blocks HTTP intake.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
jobs. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/worker/tests/features/test_f51.py`; command `python tools/run_checks.py --feature F51`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |

## Verification evidence
Build-kit coverage verified by tools/kit/verify_kit.py. Application tests have not run because this deliverable is an implementation kit. Do not report this feature as implemented until its owning prompt executes.
