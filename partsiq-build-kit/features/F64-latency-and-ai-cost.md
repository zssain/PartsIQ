# F64 Latency and AI cost

Status: specified, not implemented.

Owning prompt: `prompts/F64-latency-and-ai-cost.md`.

Behavior: Measure stages with monotonic clock; log model/token usage and estimated cost; reserve confirmed free credit before each attempt; expose consumed/reserved allowance.

Failure criteria: Unknown price or expired credit blocks calls; concurrent reservations cannot exceed cap; API key validity never implies free credit.

API operations: f64_read_allowance, f64_configure_allowance

Files:
- `apps/api/partsiq/features/f64_latency_and_ai_cost.py`
- `apps/web/src/features/f64_latency_and_ai_cost/Panel.tsx`
- `tests/features/test_f64.py`
- `apps/web/tests/features/f64.test.tsx`
- `apps/api/partsiq/api/f64_latency_and_ai_cost.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
