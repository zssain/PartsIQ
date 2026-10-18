# F42 Assignments

Status: specified, not implemented.

Owning prompt: `prompts/F42-assignments.md`.

Behavior: Admin assigns active reviewer or unassigns; persist assignment history atomically; access changes immediately; demo reviewer access remains session-scoped.

Failure criteria: Non-admin assignment denied; disabled/nonreviewer assignee rejected; previous reviewer loses access on next request.

API operations: f42_assign

Files:
- `apps/api/partsiq/features/f42_assignments.py`
- `apps/web/src/features/f42_assignments/Panel.tsx`
- `tests/features/test_f42.py`
- `apps/web/tests/features/f42.test.tsx`
- `apps/api/partsiq/api/f42_assignments.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
