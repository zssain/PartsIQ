# F53 Graceful failures

Status: specified, not implemented.

Owning prompt: `prompts/F53-graceful-failures.md`.

Behavior: Map stable error codes to bilingual recovery guidance; distinguish validation, quota, service outage and staff-required states; preserve user input.

Failure criteria: No raw stack traces or keys; retry only safe idempotent action; search lexical fallback clearly reported.

API operations: No independent endpoint

Files:
- `apps/api/partsiq/features/f53_graceful_failures.py`
- `tests/features/test_f53.py`
- `apps/web/tests/features/f53.test.tsx`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
