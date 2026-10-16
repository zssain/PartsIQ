# F48 - Input isolation

| Field | Value |
|---|---|
| Status | planned |
| Owner module(s) | services/orchestrator |
| Implementing prompts | F48; foundations 10, 11, 12, 13, 16 |
| Affected flows | FLOW.md row F48 |

## Scope
Treat customer text,OCR and imported evidence as data; separate trusted instructions; bound tool names,arguments,steps and output size; never execute model-produced templates.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Treat customer text,OCR and imported evidence as data; separate trusted instructions; bound tool names,arguments,steps and output size; never execute model-produced templates.
- [ ] Prompt injection cannot call write tools,change roles or reveal secrets; tool result with rogue instructions remains inert.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
none. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/orchestrator/tests/features/test_f48.py`; command `python tools/run_checks.py --feature F48`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |

## Verification evidence
Build-kit coverage verified by tools/kit/verify_kit.py. Application tests have not run because this deliverable is an implementation kit. Do not report this feature as implemented until its owning prompt executes.
