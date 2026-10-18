# F15 OCR confirmation

Status: specified, not implemented.

Owning prompt: `prompts/F15-ocr-confirmation.md`.

Behavior: Show cropped or original nameplate beside extracted identifiers; require user confirm or correction; record actor and time; preserve leading zeros in serial text.

Failure criteria: Unconfirmed OCR never authorizes matching; blank corrected serial triggers missing-serial flow; stale confirmation returns 409.

API operations: f15_confirm_nameplate

Files:
- `apps/api/partsiq/features/f15_ocr_confirmation.py`
- `apps/web/src/features/f15_ocr_confirmation/Panel.tsx`
- `tests/features/test_f15.py`
- `apps/web/tests/features/f15.test.tsx`
- `apps/api/partsiq/api/f15_ocr_confirmation.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
