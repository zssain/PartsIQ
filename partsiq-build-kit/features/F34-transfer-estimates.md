# F34 Transfer estimates

Status: specified, not implemented.

Owning prompt: `prompts/F34-transfer-estimates.md`.

Behavior: Carry integer transfer_days from approved route; show estimate and source warehouse; local availability means zero transfer days.

Failure criteria: No route gives unknown/unavailable plan rather than invented one-day promise; estimate labelled non-guaranteed.

API operations: f34_transfer_evidence

Files:
- `apps/api/partsiq/features/f34_transfer_estimates.py`
- `apps/web/src/features/f34_transfer_estimates/Panel.tsx`
- `tests/features/test_f34.py`
- `apps/web/tests/features/f34.test.tsx`
- `apps/api/partsiq/api/f34_transfer_estimates.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
