# F10 Structured extraction

Status: specified, not implemented.

Owning prompt: `prompts/F10-structured-extraction.md`.

Behavior: Extract item descriptions, quantities, urgency and machine hints with strict structured outputs; preserve source spans; missing quantity becomes a clarification rather than assumed order quantity.

Failure criteria: Unknown keys and invalid quantities reject the response; unsupported model output cannot progress to search.

API operations: f10_read_current

Files:
- `apps/api/partsiq/features/f10_structured_extraction.py`
- `apps/web/src/features/f10_structured_extraction/Panel.tsx`
- `tests/features/test_f10.py`
- `apps/web/tests/features/f10.test.tsx`
- `apps/api/partsiq/api/f10_structured_extraction.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
