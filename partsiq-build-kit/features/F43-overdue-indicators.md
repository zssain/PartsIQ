# F43 Overdue indicators

Status: specified, not implemented.

Owning prompt: `prompts/F43-overdue-indicators.md`.

Behavior: Set due_at using configurable urgent/normal thresholds; display overdue only for unresolved states; sort overdue first when requested; store all times UTC.

Failure criteria: Approved/rejected items never overdue; daylight-saving display does not change deadline; thresholds not described as contractual SLA.

API operations: f43_deadline

Files:
- `apps/api/partsiq/features/f43_overdue_indicators.py`
- `apps/web/src/features/f43_overdue_indicators/Panel.tsx`
- `tests/features/test_f43.py`
- `apps/web/tests/features/f43.test.tsx`
- `apps/api/partsiq/api/f43_overdue_indicators.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
