# F57 - Catalogue browser

| Field | Value |
|---|---|
| Status | planned |
| Owner module(s) | services/gateway |
| Implementing prompts | F57; foundations 02, 06, 18 |
| Affected flows | FLOW.md row F57 |

## Scope
Read published catalogue with model/category/text filters; page results; show part detail and supersession; staff can inspect fitment and sources.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Read published catalogue with model/category/text filters; page results; show part detail and supersession; staff can inspect fitment and sources.
- [ ] No unpublished import rows exposed; missing number returns 404; literal query cannot become SQL.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
parts, equipment_models. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/gateway/tests/features/test_f57.py`; command `python tools/run_checks.py --feature F57`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |

## Verification evidence
Build-kit coverage verified by tools/kit/verify_kit.py. Application tests have not run because this deliverable is an implementation kit. Do not report this feature as implemented until its owning prompt executes.
