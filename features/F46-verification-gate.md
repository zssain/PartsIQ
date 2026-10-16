# F46 - Verification gate

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/orchestrator |
| Implementing prompts | 12; foundations 12 |
| Affected flows | FLOW.md row 12 |

## Scope
Check item/configuration/candidate membership, provenance, catalogue version, selected quantities and allocation bounds; compute canonical fact hash; store named rule results.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [x] Check item/configuration/candidate membership, provenance, catalogue version, selected quantities and allocation bounds; compute canonical fact hash; store named rule results.
- [x] Unknown part, incompatible part, stale catalogue, oversold plan and hidden extra item each fail a specific rule.
- [x] Test output and implementation commit recorded before status changes to done.

## Data touched
verification_results. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/orchestrator/tests/features/test_f46.py`; command `python tools/run_checks.py --feature F46`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 12 | verification.py seven named pure checks + aggregate allocation recompute + canonical fact hash + persisted result; the five failure scenarios each fail a specific rule. | prompt/12 |

## Verification evidence
services/orchestrator/tests/features/test_f46.py PASS under the orchestrator suite (22 passed, 1 skipped) and the named checks are also covered by tests/foundations/test_12.py (24 cases); run_checks --prompt 12 exits 0; ruff clean; verify_kit PASSED. The live verification_results Postgres adapter is integration-only and remains BLOCKED (tested here through an in-memory store + typed fixtures).
