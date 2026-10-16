# F28 - Compatibility references

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/search |
| Implementing prompts | 12; foundations 02, 06, 12 |
| Affected flows | FLOW.md row 12 |

## Scope
Resolve source_reference to version-specific document and page; retain citation with every candidate and approval snapshot.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [x] Resolve source_reference to version-specific document and page; retain citation with every candidate and approval snapshot.
- [x] Missing source file blocks evidence viewer and flags review; mismatched version fails verification. (Verification half done in prompt 12: an absent/unresolvable citation flags review and a mismatched version fails the source-evidence rule; the evidence-viewer UI binding is delivered by F29.)
- [x] Test output and implementation commit recorded before status changes to done.

## Data touched
catalogue_evidence, part_compatibility. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/search/tests/features/test_f28.py`; command `python tools/run_checks.py --feature F28`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 02 | source_reference columns carried in migrated schema. Verified structurally in test_02.py. Evidence resolution owned by prompt 12/F29. | prompt/02 |
| 2026-10-17 | 12 | search_parts retains a version-specific citation with every candidate (test_f28.py); orchestrator resolve_source_reference + source-evidence rule reject blank/unresolvable or mismatched-version citations (verification.py). Evidence-viewer UI binding remains F29. | prompt/12 |

## Verification evidence
services/search/tests/features/test_f28.py PASS under the search suite (75 passed); the version-specific resolution and mismatched-version rejection are also covered by tests/foundations/test_12.py; run_checks --prompt 12 exits 0; ruff clean; verify_kit PASSED. The F29 evidence-viewer UI (open the cited document+page) is a separate feature prompt and remains unexecuted.
