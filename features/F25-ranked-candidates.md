# F25 - Ranked candidates

| Field | Value |
|---|---|
| Status | planned |
| Owner module(s) | services/search |
| Implementing prompts | 06; foundations 06 |
| Affected flows | FLOW.md row 06 |

## Scope
Return top candidates with lexical/semantic evidence and deterministic tie order; compute runner-up margin before applying response limit.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Return top candidates with lexical/semantic evidence and deterministic tie order; compute runner-up margin before applying response limit.
- [ ] Limit one still reports ambiguity; empty set returns no candidate; NaN scores rejected.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
enquiry_candidates. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/search/tests/features/test_f25.py`; command `python tools/run_checks.py --feature F25`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 06 | runner-up margin computed before response limit (limit=1 still reports ambiguity); NaN rejected; empty set zero confidence. test_f25.py + test_06.py. Live DB/BGE-M3 BLOCKED. | prompt/06 |

## Verification evidence
Build-kit coverage verified by tools/kit/verify_kit.py. Application tests have not run because this deliverable is an implementation kit. Do not report this feature as implemented until its owning prompt executes.
