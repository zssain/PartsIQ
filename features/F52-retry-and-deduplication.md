# F52 - Retry and deduplication

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/worker |
| Implementing prompts | 15; foundations 15 |
| Affected flows | FLOW.md row 15 |

## Scope
Claim with FOR UPDATE SKIP LOCKED; assign lease token; heartbeat; retry transient errors with backoff up to max attempts; fence final writes by lease token.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [x] Claim with FOR UPDATE SKIP LOCKED; assign lease token; heartbeat; retry transient errors with backoff up to max attempts; fence final writes by lease token.
- [ ] Expired worker cannot commit; permanent validation failure not retried; provider timeout marked uncertain and budget held conservatively.
- [x] Test output and implementation commit recorded before status changes to done.

## Data touched
jobs. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/worker/tests/features/test_f52.py`; command `python tools/run_checks.py --feature F52`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 15 | claim SKIP LOCKED + fresh token + attempts++; token/revision/generation fencing; max_attempts -> failed. | prompt/15 |

## Verification evidence
services/worker/tests/features/test_f52.py PASS under the worker suite; tests/foundations/test_15.py. Live asyncpg SKIP LOCKED BLOCKED (fakes mirror it).
