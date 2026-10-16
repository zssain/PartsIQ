# F67 - Traces

| Field | Value |
|---|---|
| Status | planned |
| Owner module(s) | libs/partsiq_common |
| Implementing prompts | 23; foundations 01, 09, 23 |
| Affected flows | FLOW.md row 23 |

## Scope
Propagate request/enquiry/job IDs; capture stage timing and safe status; export optional Langfuse traces with payload redaction; operate normally when tracing unavailable.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [ ] Propagate request/enquiry/job IDs; capture stage timing and safe status; export optional Langfuse traces with payload redaction; operate normally when tracing unavailable.
- [ ] No raw key or full photo logged; exporter outage never breaks approval; budget accounting remains local and authoritative.
- [ ] Test output and implementation commit recorded before status changes to done.

## Data touched
ai_usage, audit_log. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`tests/acceptance/test_f67.py`; command `python tools/run_checks.py --feature F67`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 01 | Redaction + outage-safe Tracer + request-id propagation primitives implemented; tracing optional and never breaks a call. Verified in test_01.py. Owner prompt 23 finalizes Langfuse export. | prompt/01 |

## Verification evidence
Build-kit coverage verified by tools/kit/verify_kit.py. Application tests have not run because this deliverable is an implementation kit. Do not report this feature as implemented until its owning prompt executes.
