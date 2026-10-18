# F13 Private uploads

Status: specified, not implemented.

Owning prompt: `prompts/F13-private-uploads.md`.

Behavior: Create pending attachment and unique object path; use signed upload; validate actual bytes and magic type after confirmation; strip EXIF and cap decoded pixels before OCR.

Failure criteria: Wrong MIME, oversized content, image decompression bomb, duplicate confirmation and nonexistent object handled explicitly.

API operations: f13_create_upload, f13_list_attachments

Files:
- `apps/api/partsiq/features/f13_private_uploads.py`
- `apps/web/src/features/f13_private_uploads/Panel.tsx`
- `tests/features/test_f13.py`
- `apps/web/tests/features/f13.test.tsx`
- `apps/api/partsiq/api/f13_private_uploads.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
