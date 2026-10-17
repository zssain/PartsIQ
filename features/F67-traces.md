# F67 - Traces

| Field | Value |
|---|---|
| Status | done |
| Owner module(s) | libs/partsiq_common |
| Implementing prompts | 23; foundations 01, 09, 23 |
| Affected flows | FLOW.md row 23 |

## Scope
Propagate request/enquiry/job IDs; capture stage timing and safe status; export optional Langfuse traces with payload redaction; operate normally when tracing unavailable.

## Out of scope
Voice,quotations,external messaging,payments,actual stock reservations and automatic approval are excluded.

## Acceptance criteria
- [x] Propagate request/enquiry/job IDs; capture stage timing and safe status; export optional Langfuse traces with payload redaction; operate normally when tracing unavailable.
- [ ] No raw key or full photo logged; exporter outage never breaks approval; budget accounting remains local and authoritative.
- [x] Test output and implementation commit recorded before status changes to done.

## Data touched
ai_usage, audit_log. Exact columns,keys,indexes and policies are in TECH_SPEC.md section4 and spec/sql. No feature may silently introduce a column absent from that schema.

## Tests
`tests/acceptance/test_f67.py`; command `python tools/run_checks.py --feature F67`. Live provider checks require confirmed credit and are separate from deterministic acceptance.

## Trace log
| Date | Prompt | What changed | Commit |
|---|---|---|---|
| 2026-10-11 | Build kit | Scope,owner and required tests specified | Specification artifact; application implementation not executed |
| 2026-10-17 | 23 | call_structured emits a redacted span with request/enquiry ids; LangfuseExporter optional + lazy; exporter outage never raises; budget accounting stays local/authoritative. | prompt/23 |
| 2026-10-17 | 01 | Redaction + outage-safe Tracer + request-id propagation primitives implemented; tracing optional and never breaks a call. Verified in test_01.py. Owner prompt 23 finalizes Langfuse export. | prompt/01 |

## Verification evidence
tests/acceptance/test_f67.py PASS (run_checks --feature F67) + tests/foundations/test_23.py. Live Langfuse sink BLOCKED (fake exporter used).
