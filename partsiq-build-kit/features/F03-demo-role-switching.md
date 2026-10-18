# F03 Demo role switching

Status: specified, not implemented.

Owning prompt: `prompts/F03-demo-role-switching.md`.

Behavior: Switch the presentation between customer and reviewer using the same anonymous identity and session; authorize review only for enquiries belonging to that active session.

Failure criteria: Forged reviewer role never grants staff membership; another visitor's enquiry returns 404.

API operations: No independent endpoint

Files:
- `apps/api/partsiq/features/f03_demo_role_switching.py`
- `apps/web/src/features/f03_demo_role_switching/Panel.tsx`
- `tests/features/test_f03.py`
- `apps/web/tests/features/f03.test.tsx`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
