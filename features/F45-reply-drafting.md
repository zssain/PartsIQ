# F45 - Reply drafting

| Field | Value |
|---|---|
| Status | planned |
| Owner module(s) | services/orchestrator |
| Implementing prompts | 13; foundations 13 |
| Affected flows | FLOW.md row 13 |

## Scope
Generate greeting,explanation and closing as structured slots; code inserts all numbers and allocations; choose Arabic or English from confirmed preference.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Generate greeting,explanation and closing as structured slots; code inserts all numbers and allocations; choose Arabic or English from confirmed preference.
- [ ] Unapproved critical facts never rendered; unsupported slots rejected; provider failure permits staff-authored controlled draft.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
drafts. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/orchestrator/tests/features/test_f45.py`; command `python tools/run_checks.py --feature F45`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |

## Verification evidence
Build-kit coverage verified by tools/kit/verify_kit.py. Application tests have not run because this deliverable is an implementation kit. Do not report this feature as implemented until its owning prompt executes.
