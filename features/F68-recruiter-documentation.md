# F68 - Recruiter documentation

| Field | Value |
|---|---|
| Status | planned |
| Owner module(s) | docs |
| Implementing prompts | F68; foundations 21, 22, 23, 24, 25, 26, 27 |
| Affected flows | FLOW.md row F68 |

## Scope
Write concise overview,real architecture,quick start,demo paths,tests,trade-offs and limitations; link measured evidence; explain deterministic decisions and specialist tools.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Write concise overview,real architecture,quick start,demo paths,tests,trade-offs and limitations; link measured evidence; explain deterministic decisions and specialist tools.
- [ ] No invented accuracy,uptime,client relationship or production adoption; distinguish implementation status from specification.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
none. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`tests/acceptance/test_f68.py`; command `python tools/run_checks.py --feature F68`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |

## Verification evidence
Build-kit coverage verified by tools/kit/verify_kit.py. Application tests have not run because this deliverable is an implementation kit. Do not report this feature as implemented until its owning prompt executes.
