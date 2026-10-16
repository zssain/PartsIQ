# F03 - Demo role switching

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/gateway |
| Implementing prompts | 20; foundations 07, 19, 20 |
| Affected flows | FLOW.md row 20 |

## Scope
Switch the presentation between customer and reviewer using the same anonymous identity and session; authorize review only for enquiries belonging to that active session.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [x] Switch the presentation between customer and reviewer using the same anonymous identity and session; authorize review only for enquiries belonging to that active session.
- [ ] Forged reviewer role never grants staff membership; another visitor's enquiry returns 404.
- [x] Test output and implementation commit recorded before status changes to done.

## Data touched
demo_sessions. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/gateway/tests/features/test_f03.py`; command `python tools/run_checks.py --feature F03`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 20 | gateway require_access authorizes own-active-session demo review only; forged role / foreign / stale-generation -> 404. | prompt/20 |
| 2026-10-17 | 19 | demo page uses the same anonymous session; role switching UI + authorization test (test_f03) owned by prompt 20. | prompt/19 |
| 2026-10-17 | 07 | same anonymous identity/session; review authorized only for own active session; foreign enquiry -> 404; forged reviewer role never grants membership. tests/foundations/test_07.py. Live Supabase Auth + DB BLOCKED. | prompt/07 |

## Verification evidence
services/gateway/tests/features/test_f03.py PASS (gateway suite 28). Server identity verification owned by prompt 07.
