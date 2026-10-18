# F67 Traces

Status: specified, not implemented.

Owning prompt: `prompts/F67-traces.md`.

Behavior: Propagate request/enquiry/job IDs; capture stage timing and safe status; export optional Langfuse traces with payload redaction; operate normally when tracing unavailable.

Failure criteria: No raw key or full photo logged; exporter outage never breaks approval; budget accounting remains local and authoritative.

API operations: f67_list_stages

Files:
- `apps/api/partsiq/features/f67_traces.py`
- `apps/web/src/features/f67_traces/Panel.tsx`
- `tests/features/test_f67.py`
- `apps/web/tests/features/f67.test.tsx`
- `apps/api/partsiq/api/f67_traces.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
