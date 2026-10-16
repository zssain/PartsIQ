# F01 - Branded landing

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | apps/web |
| Implementing prompts | 18; foundations 18 |
| Affected flows | FLOW.md row 18 |

## Scope
Explain the enquiry-to-approval journey; show synthetic-demo notice; expose Start demo and architecture links; display the supplied bilingual logo without stretching.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [x] Explain the enquiry-to-approval journey; show synthetic-demo notice; expose Start demo and architecture links; display the supplied bilingual logo without stretching.
- [ ] Missing repository link hides that action; logo has meaningful alternative text; no affiliation claim.
- [x] Test output and implementation commit recorded before status changes to done.

## Data touched
none. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`apps/web/tests/features/f01.test.tsx`; command `python tools/run_checks.py --feature F01`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 18 | landing page: journey, synthetic notice (no affiliation), Start demo + architecture links, repo link hidden when unset, logo alt text, no stretch. | prompt/18 |

## Verification evidence
apps/web/tests/features/f01.test.tsx PASS (4, vitest) and tests/foundations/test_18.py PASS (run_checks --prompt 18). Live Supabase Auth BLOCKED.
