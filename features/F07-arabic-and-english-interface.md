# F07 - Arabic and English interface

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | apps/web |
| Implementing prompts | F07; foundations 18, 19, 20 |
| Affected flows | FLOW.md row F07 |

## Scope
Use a locale cookie and complete en/ar message catalogs; persist preference; set document lang and dir; isolate serials, numbers and part identifiers with bdi.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Use a locale cookie and complete en/ar message catalogs; persist preference; set document lang and dir; isolate serials, numbers and part identifiers with bdi.
- [ ] Missing translation fails tests; language switch preserves enquiry ID and unsent draft; mixed Arabic identifiers remain readable.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
profiles. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`apps/web/tests/features/f07.test.tsx`; command `python tools/run_checks.py --feature F07`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | F07 | resolve_locale + en/ar catalogs + i18n/request + LocaleSwitcher + layout lang/dir | committed on prompt/12-deterministic-verification |

## Verification evidence
Application implemented: apps/web vitest 34 passed (8 files) incl. tests/features/f07.test.tsx (5 cases: locale/direction, key parity, missing-key throw, bdi isolation, draft preserved). vitest is the gate; no Python owner.
