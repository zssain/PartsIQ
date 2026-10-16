# F28 - Compatibility references

| Field | Value |
|---|---|
| Status | planned |
| Owner module(s) | services/search |
| Implementing prompts | 12; foundations 02, 06, 12 |
| Affected flows | FLOW.md row 12 |

## Scope
Resolve source_reference to version-specific document and page; retain citation with every candidate and approval snapshot.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Resolve source_reference to version-specific document and page; retain citation with every candidate and approval snapshot.
- [ ] Missing source file blocks evidence viewer and flags review; mismatched version fails verification.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
catalogue_evidence, part_compatibility. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/search/tests/features/test_f28.py`; command `python tools/run_checks.py --feature F28`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 02 | source_reference columns carried in migrated schema. Verified structurally in test_02.py. Evidence resolution owned by prompt 12/F29. | prompt/02 |

## Verification evidence
Build-kit coverage verified by tools/kit/verify_kit.py. Application tests have not run because this deliverable is an implementation kit. Do not report this feature as implemented until its owning prompt executes.
