# F60 Missing-parts queue

Status: specified, not implemented.

Owning prompt: `prompts/F60-missing-parts-queue.md`.

Behavior: Record unresolved item once; allow assigned staff to mark investigating, resolved or unavailable with note; link back to enquiry; no automatic catalogue creation.

Failure criteria: Resolved status requires staff explanation; foreign item denied; empty search result is not fabricated stock.

API operations: f60_update_missing, f60_list_missing

Files:
- `apps/api/partsiq/features/f60_missing_parts_queue.py`
- `apps/web/src/features/f60_missing_parts_queue/Panel.tsx`
- `tests/features/test_f60.py`
- `apps/web/tests/features/f60.test.tsx`
- `apps/api/partsiq/api/f60_missing_parts_queue.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
