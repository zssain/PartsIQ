# F66 - Tests and CI

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | infra |
| Implementing prompts | 25; foundations 00, 25 |
| Affected flows | FLOW.md row 25 |

## Scope
Run service-isolated Python tests,frontend checks,RLS integration and deterministic evals; build images; require explicit environment approval for deployment; pin action SHAs.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [x] Run service-isolated Python tests,frontend checks,RLS integration and deterministic evals; build images; require explicit environment approval for deployment; pin action SHAs.
- [x] No prod DB in tests; no secret available to untrusted fork jobs; failed gate blocks deployment.
- [x] Test output and implementation commit recorded before status changes to done.

## Data touched
none. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`tests/acceptance/test_f66.py`; command `python tools/run_checks.py --feature F66`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 25 | ci.yml (isolated python matrix + frontend + RLS + evals, APP_ENV=test, SHA-pinned) + deploy-backend.yml (dispatch-only, environment+INFRA_READY gate, migrate-before-activate, OIDC); check_ci_configuration enforces it. | prompt/25 |
| 2026-10-17 | 00 | Runner foundation implemented: tools/run_checks.py dispatches each test in its own process, guards against a production database, and reports BLOCKED (never passed) for missing suites. Verified by tests/foundations/test_00.py. Status stays planned; full CI (tests/acceptance/test_f66.py, images, action SHAs) is prompt 25. | prompt/00-bootstrap |

## Verification evidence
tests/acceptance/test_f66.py PASS (run_checks --feature F66) + tests/foundations/test_25.py. Live CI/GHCR/AWS runs BLOCKED; action SHAs recorded, to re-verify at setup.
