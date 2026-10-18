# F29 Evidence page viewer

Status: specified, not implemented.

Owning prompt: `prompts/F29-evidence-page-viewer.md`.

Behavior: Authorize assigned reviewer or own demo reviewer; request short-lived backend-signed PDF URL; open exact cited page; label synthetic document.

Failure criteria: Customer receives reference only; arbitrary Storage key rejected; expired link can be renewed after authorization.

API operations: f29_sign_evidence

Files:
- `apps/api/partsiq/features/f29_evidence_page_viewer.py`
- `apps/web/src/features/f29_evidence_page_viewer/Panel.tsx`
- `tests/features/test_f29.py`
- `apps/web/tests/features/f29.test.tsx`
- `apps/api/partsiq/api/f29_evidence_page_viewer.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
