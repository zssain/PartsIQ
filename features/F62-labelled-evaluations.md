# F62 - Labelled evaluations

| Field | Value |
|---|---|
| Status | planned |
| Owner module(s) | tools/evals |
| Implementing prompts | 21; foundations 21 |
| Affected flows | FLOW.md row 21 |

## Scope
Include four demos plus Arabic,typo,serial-boundary,ambiguity,stock and injection cases; record expected compatible set and clarification outcome; run deterministic suite without API calls.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Include four demos plus Arabic,typo,serial-boundary,ambiguity,stock and injection cases; record expected compatible set and clarification outcome; run deterministic suite without API calls.
- [ ] No self-reported model confidence as accuracy; evaluation fixture disjoint from examples used in prompts; failures keep actual output.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
eval_cases, eval_runs, eval_results. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`tests/acceptance/test_f62.py`; command `python tools/run_checks.py --feature F62`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |

## Verification evidence
Build-kit coverage verified by tools/kit/verify_kit.py. Application tests have not run because this deliverable is an implementation kit. Do not report this feature as implemented until its owning prompt executes.
