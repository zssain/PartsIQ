# F31 - Candidate comparison

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | apps/web |
| Implementing prompts | F31; foundations 06, 20 |
| Affected flows | FLOW.md row F31 |

## Scope
Compare two or three candidates from the same item/revision; show number, names, evidence and warehouse availability; selecting a candidate sends its ID, not browser-authored facts.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Compare two or three candidates from the same item/revision; show number, names, evidence and warehouse availability; selecting a candidate sends its ID, not browser-authored facts.
- [ ] Foreign candidate or stale revision rejected; missing attribute shown as unavailable; keyboard navigation works.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
enquiry_candidates. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`apps/web/tests/features/f31.test.tsx`; command `python tools/run_checks.py --feature F31`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | F31 | compare_candidates lib + CandidateComparison component + staff page island | committed on prompt/12-deterministic-verification |

## Verification evidence
Application implemented: apps/web vitest 29 passed (7 files) incl. tests/features/f31.test.tsx (9 cases: 2/3-way compare, missing-attr unavailable, foreign candidate, stale revision, count bounds, select-sends-id + keyboard, empty/loading). vitest is the gate; no Python owner. Live selection POST BLOCKED.
