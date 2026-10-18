# F48 Input isolation

Status: specified, not implemented.

Owning prompt: `prompts/F48-input-isolation.md`.

Behavior: Treat customer text, OCR and imported evidence as data; separate trusted instructions; bound inputs, transitions, steps and output size; never execute model-produced templates.

Failure criteria: Prompt injection cannot call privileged functions, change roles or reveal secrets; model result with rogue instructions remains inert.

API operations: No independent endpoint

Files:
- `apps/api/partsiq/features/f48_input_isolation.py`
- `tests/features/test_f48.py`
- `apps/web/tests/features/f48.test.tsx`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
