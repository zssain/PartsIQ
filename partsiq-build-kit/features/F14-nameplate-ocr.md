# F14 Nameplate OCR

Status: specified, not implemented.

Owning prompt: `prompts/F14-nameplate-ocr.md`.

Behavior: Read validated nameplate via OpenAI vision; return model_text, serial_text, issues and source attachment; persist result only with current lease and revision.

Failure criteria: Unreadable fields remain null; vision instructions in photo are untrusted; timeout is bounded and creates recoverable status.

API operations: f14_confirm_upload

Files:
- `apps/api/partsiq/features/f14_nameplate_ocr.py`
- `apps/web/src/features/f14_nameplate_ocr/Panel.tsx`
- `tests/features/test_f14.py`
- `apps/web/tests/features/f14.test.tsx`
- `apps/api/partsiq/api/f14_nameplate_ocr.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
