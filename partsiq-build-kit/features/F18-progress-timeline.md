# F18 Progress timeline

Status: specified, not implemented.

Owning prompt: `prompts/F18-progress-timeline.md`.

Behavior: Show persisted stages, wait reason and last update; poll with bounded backoff; reconnect using server state; separate waiting for customer from waiting for staff.

Failure criteria: No fake completed progress; failed poll retains last state and offers retry; hidden tabs reduce polling.

API operations: f18_read_progress

Files:
- `apps/api/partsiq/features/f18_progress_timeline.py`
- `apps/web/src/features/f18_progress_timeline/Panel.tsx`
- `tests/features/test_f18.py`
- `apps/web/tests/features/f18.test.tsx`
- `apps/api/partsiq/api/f18_progress_timeline.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
