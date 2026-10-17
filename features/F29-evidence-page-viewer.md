# F29 - Evidence page viewer

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/gateway |
| Implementing prompts | F29; foundations 04, 06, 20 |
| Affected flows | FLOW.md row F29 |

## Scope
Authorize assigned reviewer or own demo reviewer; request short-lived worker-signed PDF URL; open exact cited page; label synthetic document.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Authorize assigned reviewer or own demo reviewer; request short-lived worker-signed PDF URL; open exact cited page; label synthetic document.
- [ ] Customer receives reference only; arbitrary Storage key rejected; expired link can be renewed after authorization.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
catalogue_evidence. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/gateway/tests/features/test_f29.py`; command `python tools/run_checks.py --feature F29`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | F29 | open_evidence authorize+sign + POST /v1/staff/evidence/open + web EvidenceViewer/lib | committed on prompt/12-deterministic-verification |

## Verification evidence
Application implemented: gateway suite 87 passed incl. services/gateway/tests/features/test_f29.py (8 cases). ruff clean; apps/web vitest 20. Worker signer + access adapter BLOCKED.
