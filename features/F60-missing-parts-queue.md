# F60 - Missing-parts queue

| Field | Value |
|---|---|
| Status | planned |
| Owner module(s) | services/gateway |
| Implementing prompts | F60; foundations 03, 20 |
| Affected flows | FLOW.md row F60 |

## Scope
Record unresolved item once; allow assigned staff to mark investigating,resolved or unavailable with note; link back to enquiry; no automatic catalogue creation.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Record unresolved item once; allow assigned staff to mark investigating,resolved or unavailable with note; link back to enquiry; no automatic catalogue creation.
- [ ] Resolved status requires staff explanation; foreign item denied; empty search result is not fabricated stock.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
missing_part_requests. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/gateway/tests/features/test_f60.py`; command `python tools/run_checks.py --feature F60`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |

## Verification evidence
Build-kit coverage verified by tools/kit/verify_kit.py. Application tests have not run because this deliverable is an implementation kit. Do not report this feature as implemented until its owning prompt executes.
