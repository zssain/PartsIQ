# F51 Background jobs

Status: specified, not implemented.

Owning prompt: `prompts/F51-background-jobs.md`.

Behavior: Persist job before Redis dispatch; dispatcher claims by ID; sweeper redispatches pending/expired jobs; worker handles OCR, PDF, imports and cleanup.

Failure criteria: Redis loss does not lose DB job; unavailable Redis rate limiter fails closed; heavy work never blocks HTTP intake.

API operations: f51_get_status

Files:
- `apps/api/partsiq/features/f51_background_jobs.py`
- `apps/web/src/features/f51_background_jobs/Panel.tsx`
- `tests/features/test_f51.py`
- `apps/web/tests/features/f51.test.tsx`
- `apps/api/partsiq/api/f51_background_jobs.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
