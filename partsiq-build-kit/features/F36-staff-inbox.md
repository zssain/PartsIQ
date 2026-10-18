# F36 Staff inbox

Status: specified, not implemented.

Owning prompt: `prompts/F36-staff-inbox.md`.

Behavior: List assigned operational enquiries and own active demo enquiries; filter status, priority, overdue and text; paginate stably; show counts in same access scope.

Failure criteria: Unassigned real enquiries hidden from reviewer; admin can see all; filters do not leak global counts.

API operations: f36_list_assigned

Files:
- `apps/api/partsiq/features/f36_staff_inbox.py`
- `apps/web/src/features/f36_staff_inbox/Panel.tsx`
- `tests/features/test_f36.py`
- `apps/web/tests/features/f36.test.tsx`
- `apps/api/partsiq/api/f36_staff_inbox.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
