# F41 Internal notes

Status: specified, not implemented.

Owning prompt: `prompts/F41-internal-notes.md`.

Behavior: Append reviewer notes with author and timestamp; show only in staff workspace; prohibit customer/PDF exposure; escape rendered content.

Failure criteria: Empty or over-4000-character note rejected; customer route never includes note text; unassigned staff denied.

API operations: f41_append_note, f41_list_notes

Files:
- `apps/api/partsiq/features/f41_internal_notes.py`
- `apps/web/src/features/f41_internal_notes/Panel.tsx`
- `tests/features/test_f41.py`
- `apps/web/tests/features/f41.test.tsx`
- `apps/api/partsiq/api/f41_internal_notes.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
