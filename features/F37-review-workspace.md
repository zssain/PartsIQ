# F37 - Review workspace

| Field | Value |
|---|---|
| Status | planned |
| Owner module(s) | apps/web |
| Implementing prompts | 20; foundations 20 |
| Affected flows | FLOW.md row 20 |

## Scope
Assemble current extraction, items, candidates, evidence, stock, draft and timeline; show verification failures; separate staff-only notes from customer messages.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Assemble current extraction, items, candidates, evidence, stock, draft and timeline; show verification failures; separate staff-only notes from customer messages.
- [ ] Missing panels show explicit empty states; stale revision disables approval; unassigned reviewer receives 404.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
drafts, verification_results. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`apps/web/tests/features/f37.test.tsx`; command `python tools/run_checks.py --feature F37`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |

## Verification evidence
Build-kit coverage verified by tools/kit/verify_kit.py. Application tests have not run because this deliverable is an implementation kit. Do not report this feature as implemented until its owning prompt executes.
