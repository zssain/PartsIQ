# F64 - Latency and AI cost

| Field | Value |
|---|---|
| Status | planned |
| Owner module(s) | libs/partsiq_common |
| Implementing prompts | 23; foundations 01, 23 |
| Affected flows | FLOW.md row 23 |

## Scope
Measure stages with monotonic clock; log model/token usage and estimated cost; reserve confirmed free credit before each attempt; expose consumed/reserved allowance.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Measure stages with monotonic clock; log model/token usage and estimated cost; reserve confirmed free credit before each attempt; expose consumed/reserved allowance.
- [ ] Unknown price or expired credit blocks calls; concurrent reservations cannot exceed cap; API key validity never implies free credit.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
ai_usage, ai_budget_accounts. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`tests/acceptance/test_f64.py`; command `python tools/run_checks.py --feature F64`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |

## Verification evidence
Build-kit coverage verified by tools/kit/verify_kit.py. Application tests have not run because this deliverable is an implementation kit. Do not report this feature as implemented until its owning prompt executes.
