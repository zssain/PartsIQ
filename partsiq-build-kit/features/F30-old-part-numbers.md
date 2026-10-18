# F30 Old part numbers

Status: specified, not implemented.

Owning prompt: `prompts/F30-old-part-numbers.md`.

Behavior: Follow supersession chain with cycle protection; display old and current numbers; verify current successor has explicit fitment for resolved configuration.

Failure criteria: Cycles rejected; inactive terminal part returns unavailable; inherited compatibility without source is rejected.

API operations: f30_resolve_supersession

Files:
- `apps/api/partsiq/features/f30_old_part_numbers.py`
- `apps/web/src/features/f30_old_part_numbers/Panel.tsx`
- `tests/features/test_f30.py`
- `apps/web/tests/features/f30.test.tsx`
- `apps/api/partsiq/api/f30_old_part_numbers.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
