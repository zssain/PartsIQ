# F56 - Repeat enquiry

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | services/gateway |
| Implementing prompts | F56; foundations 09, 19 |
| Affected flows | FLOW.md row F56 |

## Scope
Copy customer request and confirmed hints into a new enquiry; issue new ID/revision; link origin in audit; run matching,stock and review again.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Copy customer request and confirmed hints into a new enquiry; issue new ID/revision; link origin in audit; run matching,stock and review again.
- [ ] Never copy approval,allocation,draft or signed file URL; source ownership required; repeated submission deduplicated.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
enquiries, enquiry_items. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`services/gateway/tests/features/test_f56.py`; command `python tools/run_checks.py --feature F56`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | F56 | repeat_enquiry use case + POST /v1/enquiries/{id}/repeat + web RepeatEnquiry/lib | committed on prompt/12-deterministic-verification |

## Verification evidence
Application implemented: gateway suite 61 passed incl. services/gateway/tests/features/test_f56.py (5 cases: fresh id/revision + origin audit + pipeline re-run, outcome fields structurally absent, source-ownership 404, idempotent dedup, dependency failure). ruff clean; apps/web vitest 20 passed. Live adapter + enqueue BLOCKED.
