# F61 Enquiry PDF

Status: specified, not implemented.

Owning prompt: `prompts/F61-enquiry-pdf.md`.

Behavior: Export approved revision only; render logo, bilingual customer text, verified selections, estimates and references; embed Arabic fonts; store private object and signed download.

Failure criteria: Exclude notes and secrets; stale or unapproved revision rejected; long Arabic names wrap without clipping; no prices or quotation title.

API operations: f61_request_pdf, f61_sign_download

Files:
- `apps/api/partsiq/features/f61_enquiry_pdf.py`
- `apps/web/src/features/f61_enquiry_pdf/Panel.tsx`
- `tests/features/test_f61.py`
- `apps/web/tests/features/f61.test.tsx`
- `apps/api/partsiq/api/f61_enquiry_pdf.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
