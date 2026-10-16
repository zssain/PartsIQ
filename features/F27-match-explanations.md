# F27 - Match explanations

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | apps/web |
| Implementing prompts | 20; foundations 06, 20 |
| Affected flows | FLOW.md row 20 |

## Scope
Show actual alias, machine configuration, supersession chain and fitment reference; derive explanations from search evidence rather than invented model prose.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [x] Show actual alias, machine configuration, supersession chain and fitment reference; derive explanations from search evidence rather than invented model prose.
- [ ] Absent evidence shown as unavailable; user HTML is escaped; scores never labelled calibrated probability.
- [x] Test output and implementation commit recorded before status changes to done.

## Data touched
enquiry_candidates. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`apps/web/tests/features/f27.test.tsx`; command `python tools/run_checks.py --feature F27`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 20 | candidates show evidence-derived reasons + fitment reference; absent evidence -> unavailable; HTML escaped; score labelled a match score, not a probability. | prompt/20 |

## Verification evidence
apps/web/tests/features/f27.test.tsx PASS (vitest). Reasons/source_reference come from search evidence (prompt 06).
