# F27 - Match explanations

| Field | Value |
|---|---|
| Status | planned |
| Owner module(s) | apps/web |
| Implementing prompts | 20; foundations 06, 20 |
| Affected flows | FLOW.md row 20 |

## Scope
Show actual alias, machine configuration, supersession chain and fitment reference; derive explanations from search evidence rather than invented model prose.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Show actual alias, machine configuration, supersession chain and fitment reference; derive explanations from search evidence rather than invented model prose.
- [ ] Absent evidence shown as unavailable; user HTML is escaped; scores never labelled calibrated probability.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
enquiry_candidates. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`apps/web/tests/features/f27.test.tsx`; command `python tools/run_checks.py --feature F27`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |

## Verification evidence
Build-kit coverage verified by tools/kit/verify_kit.py. Application tests have not run because this deliverable is an implementation kit. Do not report this feature as implemented until its owning prompt executes.
