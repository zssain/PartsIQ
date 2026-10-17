# F68 - Recruiter documentation

| Field | Value |
|---|---|
| Status | done |
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
| 2026-10-17 | F68 | docs/RECRUITER_GUIDE.md (honest overview, no invented claims, impl-vs-spec) + README link | committed on prompt/12-deterministic-verification |

## Verification evidence
Application implemented: run_checks --feature F68 -> tests/acceptance/test_f68.py PASS (6 cases). ruff clean. python-docx authorized but not installed (no consumer; markdown deliverable) — documented deviation.
