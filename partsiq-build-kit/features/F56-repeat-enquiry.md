# F56 Repeat enquiry

Status: specified, not implemented.

Owning prompt: `prompts/F56-repeat-enquiry.md`.

Behavior: Copy customer request and confirmed hints into a new enquiry; issue new ID/revision; link origin in audit; run matching, stock and review again.

Failure criteria: Never copy approval, allocation, draft or signed file URL; source ownership required; repeated submission deduplicated.

API operations: f56_repeat_enquiry

Files:
- `apps/api/partsiq/features/f56_repeat_enquiry.py`
- `apps/web/src/features/f56_repeat_enquiry/Panel.tsx`
- `tests/features/test_f56.py`
- `apps/web/tests/features/f56.test.tsx`
- `apps/api/partsiq/api/f56_repeat_enquiry.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
