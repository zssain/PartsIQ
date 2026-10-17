# F59 - Catalogue versioning

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | tools/catalog |
| Implementing prompts | F59; foundations 02, 05, 06 |
| Affected flows | FLOW.md row F59 |

## Scope
Snapshot validated catalogue canonically; hash records; serialize publication; preserve numeric IDs; atomically retire old version and activate new; invalidate pending enquiries on next action.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Snapshot validated catalogue canonically; hash records; serialize publication; preserve numeric IDs; atomically retire old version and activate new; invalidate pending enquiries on next action.
- [ ] Two publishers cannot leave two active versions; failed publish rolls back; old approval retains immutable evidence snapshot.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
catalogue_versions, catalogue_records. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`tests/acceptance/test_f59.py`; command `python tools/run_checks.py --feature F59`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | F59 | publish_version + canonical_snapshot + worker publish job + gateway queue route + CLI snapshot + web | committed on prompt/12-deterministic-verification |

## Verification evidence
Application implemented: run_checks --feature F59 -> tests/acceptance/test_f59.py PASS (8 cases). worker 33; gateway 61; ruff clean; apps/web vitest 20. Live catalogue-role DB publication (advisory lock + single tx) and worker execution BLOCKED.
