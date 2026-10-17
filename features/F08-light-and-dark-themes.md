# F08 - Light and dark themes

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | apps/web |
| Implementing prompts | F08; foundations 18 |
| Affected flows | FLOW.md row F08 |

## Scope
Use CSS semantic tokens; initialize from saved preference then system setting; expose accessible toggle; honor reduced motion and browser color-scheme.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Use CSS semantic tokens; initialize from saved preference then system setting; expose accessible toggle; honor reduced motion and browser color-scheme.
- [ ] No hydration mismatch; chart colors and focus rings meet contrast checks; storage-disabled browsers still work.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
none. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`apps/web/tests/features/f08.test.tsx`; command `python tools/run_checks.py --feature F08`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | F08 | resolve_theme + ThemeToggle + dark tokens/focus/reduced-motion + no-flash layout script | committed on prompt/12-deterministic-verification |

## Verification evidence
Application implemented: apps/web vitest 38 passed (9 files) incl. tests/features/f08.test.tsx (4 cases: saved precedence, system fallback, toggle persists, storage-disabled). vitest is the gate.
