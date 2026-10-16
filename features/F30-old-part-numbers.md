# F30 - Old part numbers

| Field | Value |
|---|---|
| Status | planned |
| Owner module(s) | services/search |
| Implementing prompts | 06; foundations 02, 06 |
| Affected flows | FLOW.md row 06 |

## Scope
Follow supersession chain with cycle protection; display old and current numbers; verify current successor has explicit fitment for resolved configuration.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Follow supersession chain with cycle protection; display old and current numbers; verify current successor has explicit fitment for resolved configuration.
- [ ] Cycles rejected; inactive terminal part returns unavailable; inherited compatibility without source is rejected.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
part_supersessions. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/search/tests/features/test_f30.py`; command `python tools/run_checks.py --feature F30`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 06 | supersession successor offered only with explicit terminal fitment (ADR-018); inherited-only rejected; old number displayed. test_f30.py + test_06.py. Live DB/BGE-M3 BLOCKED. | prompt/06 |
| 2026-10-17 | 02 | part_supersessions + WITH RECURSIVE cycle protection migrated verbatim; part_number_key normalization present. Verified structurally in test_02.py. Chain-following owned by prompt 06. | prompt/02 |

## Verification evidence
Build-kit coverage verified by tools/kit/verify_kit.py. Application tests have not run because this deliverable is an implementation kit. Do not report this feature as implemented until its owning prompt executes.
