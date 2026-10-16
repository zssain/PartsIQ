# F24 - Semantic retrieval

| Field | Value |
|---|---|
| Status | planned |
| Owner module(s) | services/search |
| Implementing prompts | 06; foundations 06 |
| Affected flows | FLOW.md row 06 |

## Scope
Load one BGE-M3 encoder per search process; use normalized 1024-d vectors; retain legacy weighted fusion; fall back to lexical on unavailable embedding path.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Load one BGE-M3 encoder per search process; use normalized 1024-d vectors; retain legacy weighted fusion; fall back to lexical on unavailable embedding path.
- [ ] Wrong dimension rejected; no model loaded in worker; no semantic candidate outside compatible IDs.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
part_embeddings. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/search/tests/features/test_f24.py`; command `python tools/run_checks.py --feature F24`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 06 | 1024-d unit-norm/NaN validation; lexical fallback when no provider; embed_version ingestion with source hash. test_f24.py. Real BGE-M3 load BLOCKED. Live DB/BGE-M3 BLOCKED. | prompt/06 |

## Verification evidence
Build-kit coverage verified by tools/kit/verify_kit.py. Application tests have not run because this deliverable is an implementation kit. Do not report this feature as implemented until its owning prompt executes.
