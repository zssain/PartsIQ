# F55 - Saved machines

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/gateway |
| Implementing prompts | F55; foundations 07, 19 |
| Affected flows | FLOW.md row F55 |

## Scope
Save confirmed model and serial with user label; list own active entries; archive entry; prefill a new enquiry but re-identify against current catalogue.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Save confirmed model and serial with user label; list own active entries; archive entry; prefill a new enquiry but re-identify against current catalogue.
- [ ] Duplicate label permitted with distinct ID; foreign ID denied; stale configuration never reused as authoritative.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
saved_machines. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/gateway/tests/features/test_f55.py`; command `python tools/run_checks.py --feature F55`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | F55 | save/list/rename/archive use cases + /v1/machines routes + web SavedMachines/lib | committed on prompt/12-deterministic-verification |

## Verification evidence
Application implemented: gateway suite 56 passed incl. services/gateway/tests/features/test_f55.py (12 cases: verbatim serial, idempotent save, duplicate-label distinct id, blank label/serial & non-positive model 422, dependency failure, list excludes foreign+archived, rename label-only, foreign rename/archive 404, prefill identifiers-only). ruff clean; apps/web vitest 20 passed. Live adapter + RLS BLOCKED.
