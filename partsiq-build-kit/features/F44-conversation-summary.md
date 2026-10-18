# F44 Conversation summary

Status: specified, not implemented.

Owning prompt: `prompts/F44-conversation-summary.md`.

Behavior: Produce staff-only concise summary from authorized messages and confirmed fields; store message IDs and revision; use shared budget wrapper; regenerate on relevant change.

Failure criteria: Outdated summary labelled stale; instructions inside messages ignored; exhausted budget leaves full conversation available.

API operations: f44_enqueue_summary, f44_read_summary

Files:
- `apps/api/partsiq/features/f44_conversation_summary.py`
- `apps/web/src/features/f44_conversation_summary/Panel.tsx`
- `tests/features/test_f44.py`
- `apps/web/tests/features/f44.test.tsx`
- `apps/api/partsiq/api/f44_conversation_summary.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
