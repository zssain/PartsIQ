# F09 Bilingual chat

Status: specified, not implemented.

Owning prompt: `prompts/F09-bilingual-chat.md`.

Behavior: Accept Arabic, English and mixed text; preserve original message; detect preferred reply locale; render customer messages immediately after successful persistence.

Failure criteria: Empty and oversized input returns validation error; HTML is escaped; retry does not duplicate a message.

API operations: f09_create_enquiry, f09_get_enquiry

Files:
- `apps/api/partsiq/features/f09_bilingual_chat.py`
- `apps/web/src/features/f09_bilingual_chat/Panel.tsx`
- `tests/features/test_f09.py`
- `apps/web/tests/features/f09.test.tsx`
- `apps/api/partsiq/api/f09_bilingual_chat.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
