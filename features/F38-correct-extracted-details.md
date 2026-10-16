# F38 - Correct extracted details

| Field | Value |
|---|---|
| Status | planned |
| Owner module(s) | services/orchestrator |
| Implementing prompts | F38; foundations 09, 14, 20 |
| Affected flows | FLOW.md row F38 |

## Scope
Lock enquiry; compare expected revision; apply typed allowed corrections; increment revision; invalidate derived selections/draft/approval; enqueue recomputation; record before and after.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Lock enquiry; compare expected revision; apply typed allowed corrections; increment revision; invalidate derived selections/draft/approval; enqueue recomputation; record before and after.
- [ ] Unknown field rejected; old revision returns 409; correction cannot directly set approved status or invent candidate facts.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
enquiry_revisions, correction_records. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/orchestrator/tests/features/test_f38.py`; command `python tools/run_checks.py --feature F38`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |

## Verification evidence
Build-kit coverage verified by tools/kit/verify_kit.py. Application tests have not run because this deliverable is an implementation kit. Do not report this feature as implemented until its owning prompt executes.
