# F26 Ambiguity handling

Status: specified, not implemented.

Owning prompt: `prompts/F26-ambiguity-handling.md`.

Behavior: Use tested score and margin thresholds in code; ask customer to distinguish fuel filter versus separator; allow staff to select only verified candidates.

Failure criteria: LLM cannot override low confidence; unavailable candidate choice returns 409; thresholds evaluated on labelled cases.

API operations: f26_choose_candidate

Files:
- `apps/api/partsiq/features/f26_ambiguity_handling.py`
- `apps/web/src/features/f26_ambiguity_handling/Panel.tsx`
- `tests/features/test_f26.py`
- `apps/web/tests/features/f26.test.tsx`
- `apps/api/partsiq/api/f26_ambiguity_handling.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
