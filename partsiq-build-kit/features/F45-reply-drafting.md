# F45 Reply drafting

Status: specified, not implemented.

Owning prompt: `prompts/F45-reply-drafting.md`.

Behavior: Generate greeting, explanation and closing as structured slots; code inserts all numbers and allocations; choose Arabic or English from confirmed preference.

Failure criteria: Unapproved critical facts never rendered; unsupported slots rejected; provider failure permits staff-authored controlled draft.

API operations: f45_save_slots

Files:
- `apps/api/partsiq/features/f45_reply_drafting.py`
- `apps/web/src/features/f45_reply_drafting/Panel.tsx`
- `tests/features/test_f45.py`
- `apps/web/tests/features/f45.test.tsx`
- `apps/api/partsiq/api/f45_reply_drafting.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
