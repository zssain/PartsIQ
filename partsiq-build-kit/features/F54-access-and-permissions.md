# F54 Access and permissions

Status: specified, not implemented.

Owning prompt: `prompts/F54-access-and-permissions.md`.

Behavior: Verify Supabase issuer, audience, signature, expiry; derive identity server-side; enforce assigned-only review; keep credentials server-side; disable public real-client signup.

Failure criteria: Forged role claim ignored; missing context denies rows; preview cannot reach prod database; demo cannot publish shared catalogue.

API operations: f54_identity

Files:
- `apps/api/partsiq/features/f54_access_and_permissions.py`
- `apps/web/src/features/f54_access_and_permissions/Panel.tsx`
- `tests/features/test_f54.py`
- `apps/web/tests/features/f54.test.tsx`
- `apps/api/partsiq/api/f54_access_and_permissions.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
