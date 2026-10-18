# F12 Conversation memory

Status: specified, not implemented.

Owning prompt: `prompts/F12-conversation-memory.md`.

Behavior: Persist all messages and typed current state; compact context using retained structured facts; resume by enquiry/revision; never mix customer sessions.

Failure criteria: Restart retains unresolved questions; old revision events are ignored and audited; foreign thread ID denied.

API operations: f12_list_messages

Files:
- `apps/api/partsiq/features/f12_conversation_memory.py`
- `apps/web/src/features/f12_conversation_memory/Panel.tsx`
- `tests/features/test_f12.py`
- `apps/web/tests/features/f12.test.tsx`
- `apps/api/partsiq/api/f12_conversation_memory.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
