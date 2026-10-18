# F11 Clarifying questions

Status: specified, not implemented.

Owning prompt: `prompts/F11-clarifying-questions.md`.

Behavior: Use workflow reason codes to choose code-owned bilingual questions; persist pending question; associate answer with item; rerun affected resolution only.

Failure criteria: No final recommendation before approval; contradictory answer requires confirmation; repeat event creates one question.

API operations: f11_append_message

Files:
- `apps/api/partsiq/features/f11_clarifying_questions.py`
- `apps/web/src/features/f11_clarifying_questions/Panel.tsx`
- `tests/features/test_f11.py`
- `apps/web/tests/features/f11.test.tsx`
- `apps/api/partsiq/api/f11_clarifying_questions.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
