# F19 Enquiry history

Status: specified, not implemented.

Owning prompt: `prompts/F19-enquiry-history.md`.

Behavior: Return cursor-paginated owned history with status and created time; filter active demo generation; link to full conversation; use stable created_at/id ordering.

Failure criteria: Foreign owner ID ignored; invalid cursor returns 422; equal timestamps do not duplicate or skip records.

API operations: f19_list_enquiries

Files:
- `apps/api/partsiq/features/f19_enquiry_history.py`
- `apps/web/src/features/f19_enquiry_history/Panel.tsx`
- `tests/features/test_f19.py`
- `apps/web/tests/features/f19.test.tsx`
- `apps/api/partsiq/api/f19_enquiry_history.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
