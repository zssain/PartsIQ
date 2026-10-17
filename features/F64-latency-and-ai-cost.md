# F64 - Latency and AI cost

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | libs/partsiq_common |
| Implementing prompts | 23; foundations 01, 23 |
| Affected flows | FLOW.md row 23 |

## Scope
Measure stages with monotonic clock; log model/token usage and estimated cost; reserve confirmed free credit before each attempt; expose consumed/reserved allowance.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [x] Measure stages with monotonic clock; log model/token usage and estimated cost; reserve confirmed free credit before each attempt; expose consumed/reserved allowance.
- [ ] Unknown price or expired credit blocks calls; concurrent reservations cannot exceed cap; API key validity never implies free credit.
- [x] Test output and implementation commit recorded before status changes to done.

## Data touched
ai_usage, ai_budget_accounts. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`tests/acceptance/test_f64.py`; command `python tools/run_checks.py --feature F64`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 23 | monotonic Stage timing; reserve_for_request worst-case atomic reservation; unknown price/expired/disabled block; key never implies credit; consumed/reserved exposed. | prompt/23 |
| 2026-10-17 | 01 | Budget allowance gate + prices.json + monotonic staging implemented: paid budget must be 0, unknown price/expired credit block, atomic caps. Verified in test_01.py. Owner prompt 23 finalizes metrics. | prompt/01 |

## Verification evidence
tests/acceptance/test_f64.py PASS (run_checks --feature F64) + tests/foundations/test_23.py. Live metrics DB BLOCKED.
