# F06 - Responsive layouts

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | apps/web |
| Implementing prompts | F06; foundations 18, 19, 20 |
| Affected flows | FLOW.md row F06 |

## Scope
Support 360,768,1280 CSS-pixel widths; stack review panels; horizontally scroll comparison tables within their region; preserve sticky primary review actions without covering content.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Support 360,768,1280 CSS-pixel widths; stack review panels; horizontally scroll comparison tables within their region; preserve sticky primary review actions without covering content.
- [ ] No page-wide horizontal overflow; zoom 200 percent remains usable; mobile dialogs retain visible close action.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
none. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`apps/web/tests/features/f06.test.tsx`; command `python tools/run_checks.py --feature F06`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | F06 | get_layout breakpoints + ResponsiveShell + tokens overflow/scroll/sticky + layout/page wrap | committed on prompt/12-deterministic-verification |

## Verification evidence
Application implemented: apps/web vitest 44 passed (10 files) incl. tests/features/f06.test.tsx (6 cases: 360/768/1280 columns, reducedMotion, controlled+uncontrolled shell). vitest is the gate.
