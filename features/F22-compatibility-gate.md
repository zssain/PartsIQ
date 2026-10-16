# F22 - Compatibility gate

| Field | Value |
|---|---|
| Status | planned |
| Owner module(s) | services/search |
| Implementing prompts | 06; foundations 02, 06 |
| Affected flows | FLOW.md row 06 |

## Scope
Fetch authoritative fitment set first; rank only members; carry source_reference and catalogue version through every candidate.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Fetch authoritative fitment set first; rank only members; carry source_reference and catalogue version through every candidate.
- [ ] A perfect lexical match outside fitment is absent; empty fitment returns unavailable; blank provenance cannot be published.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
part_compatibility. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/search/tests/features/test_f22.py`; command `python tools/run_checks.py --feature F22`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 02 | part_compatibility relation migrated verbatim as the authoritative fitment source. Verified structurally in test_02.py. Ranking-over-members owned by prompt 06. | prompt/02 |

## Verification evidence
Build-kit coverage verified by tools/kit/verify_kit.py. Application tests have not run because this deliverable is an implementation kit. Do not report this feature as implemented until its owning prompt executes.
