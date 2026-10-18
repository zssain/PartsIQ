# F38 Correct extracted details

Status: specified, not implemented.

Owning prompt: `prompts/F38-correct-extracted-details.md`.

Behavior: Lock enquiry; compare expected revision; apply typed allowed corrections; increment revision; invalidate derived selections/draft/approval; enqueue recomputation; record before and after.

Failure criteria: Unknown field rejected; old revision returns 409; correction cannot directly set approved status or invent candidate facts.

API operations: f38_correct_extraction

Files:
- `apps/api/partsiq/features/f38_correct_extracted_details.py`
- `apps/web/src/features/f38_correct_extracted_details/Panel.tsx`
- `tests/features/test_f38.py`
- `apps/web/tests/features/f38.test.tsx`
- `apps/api/partsiq/api/f38_correct_extracted_details.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
