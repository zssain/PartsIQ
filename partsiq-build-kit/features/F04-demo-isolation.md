# F04 Demo isolation

Status: specified, not implemented.

Owning prompt: `prompts/F04-demo-isolation.md`.

Behavior: Bind each session to verified anonymous Supabase identity; check generation and expiry on every read, write and worker completion; exclude demos from operational metrics by default.

Failure criteria: Expired, reset and foreign sessions fail; missing identity context returns no rows.

API operations: f04_require_demo_session, f04_create_session

Files:
- `apps/api/partsiq/features/f04_demo_isolation.py`
- `apps/web/src/features/f04_demo_isolation/Panel.tsx`
- `tests/features/test_f04.py`
- `apps/web/tests/features/f04.test.tsx`
- `apps/api/partsiq/api/f04_demo_isolation.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
