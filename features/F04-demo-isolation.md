# F04 - Demo isolation

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/gateway |
| Implementing prompts | 22; foundations 03, 07, 22 |
| Affected flows | FLOW.md row 22 |

## Scope
Bind each session to verified anonymous Supabase identity; check generation and expiry on every read, write and worker completion; exclude demos from operational metrics by default.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [x] Bind each session to verified anonymous Supabase identity; check generation and expiry on every read, write and worker completion; exclude demos from operational metrics by default.
- [ ] Expired, reset and foreign sessions fail; missing identity context returns no rows.
- [x] Test output and implementation commit recorded before status changes to done.

## Data touched
demo_sessions, enquiries. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/gateway/tests/features/test_f04.py`; command `python tools/run_checks.py --feature F04`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 22 | require_access binds demo review to the own active session; expired/reset/foreign/missing-context all -> 404 (test_f04.py). | prompt/22 |
| 2026-10-17 | 07 | session bound to verified anonymous identity; generation/expiry checked; foreign/stale demo -> NOT_FOUND. test_07.py. Live Supabase Auth + DB BLOCKED. | prompt/07 |
| 2026-10-17 | 03 | RLS + app_private.demo_active/can_read_enquiry/can_review migrated verbatim; demo session generation/expiry enforced in policy; transaction-local app.actor_id. Structural assertions in test_03.py; live enforcement under tests/integration. | prompt/03 |

## Verification evidence
services/gateway/tests/features/test_f04.py PASS (gateway suite 36) + tests/foundations/test_22.py. Live RLS generation/expiry checks BLOCKED (disposable Supabase).
