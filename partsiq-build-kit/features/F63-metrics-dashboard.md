# F63 Metrics dashboard

Status: specified, not implemented.

Owning prompt: `prompts/F63-metrics-dashboard.md`.

Behavior: Show volume, status, review time, clarification and labelled accuracy with denominators; separate demo traffic; filter time window; scope reviewer data to assignments. Export redacted aggregate events to Snowflake through an outbox and show reporting freshness separately from live operational counts.

Failure criteria: Zero denominator displays unavailable; no fabricated percentage; demo traffic never silently improves operational metrics.

API operations: f63_metrics, f63_read_sync

Files:
- `apps/api/partsiq/features/f63_metrics_dashboard.py`
- `apps/web/src/features/f63_metrics_dashboard/Panel.tsx`
- `tests/features/test_f63.py`
- `apps/web/tests/features/f63.test.tsx`
- `apps/api/partsiq/api/f63_metrics_dashboard.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
