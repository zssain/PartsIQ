# F54 - Access and permissions

| Field | Value |
|---|---|
| Status | planned |
| Owner module(s) | services/gateway |
| Implementing prompts | 22; foundations 07, 18, 22 |
| Affected flows | FLOW.md row 22 |

## Scope
Verify Supabase issuer,audience,signature,expiry; derive identity server-side; enforce assigned-only review; keep credentials server-side; disable public real-client signup.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Verify Supabase issuer,audience,signature,expiry; derive identity server-side; enforce assigned-only review; keep credentials server-side; disable public real-client signup.
- [ ] Forged role claim ignored; missing context denies rows; preview cannot reach prod database; demo cannot publish shared catalogue.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
profiles, staff_roles. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/gateway/tests/features/test_f54.py`; command `python tools/run_checks.py --feature F54`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 18 | web half: bearer in Authorization header (not URL), only public NEXT_PUBLIC_* Supabase values in the browser, no secret in apps/web, no public real-client signup (tests/foundations/test_18.py). Server verification owned by 07/22. | prompt/18 |
| 2026-10-17 | 07 | Supabase issuer/audience/expiry/algorithm verified via cached JWKS (refresh-once); roles from DB not JWT; assigned-only real review; forged role ignored. test_07.py. Live Supabase Auth + DB BLOCKED. | prompt/07 |

## Verification evidence
Build-kit coverage verified by tools/kit/verify_kit.py. Application tests have not run because this deliverable is an implementation kit. Do not report this feature as implemented until its owning prompt executes.
