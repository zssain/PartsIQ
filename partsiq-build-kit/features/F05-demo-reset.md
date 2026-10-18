# F05 Demo reset

Status: specified, not implemented.

Owning prompt: `prompts/F05-demo-reset.md`.

Behavior: Lock session; increment generation; cancel unfinished jobs from prior generation; enqueue Storage cleanup; keep minimal audit; create fresh scenario enquiries on explicit selection.

Failure criteria: Late OCR from old generation cannot update current data; repeated reset idempotency key returns the same generation.

API operations: f05_reset_session

Files:
- `apps/api/partsiq/features/f05_demo_reset.py`
- `apps/web/src/features/f05_demo_reset/Panel.tsx`
- `tests/features/test_f05.py`
- `apps/web/tests/features/f05.test.tsx`
- `apps/api/partsiq/api/f05_demo_reset.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
