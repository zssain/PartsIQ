# F16 Photo quality feedback

Status: specified, not implemented.

Owning prompt: `prompts/F16-photo-quality-feedback.md`.

Behavior: Check decodability, dimensions and blur heuristic before paid call; return actionable retake instructions; mark heuristic as advisory; allow a readable image despite noncritical blur warning.

Failure criteria: Unsupported format rejected; dark or low-resolution sample gets guidance; no fabricated OCR confidence percentage.

API operations: f16_read_quality

Files:
- `apps/api/partsiq/features/f16_photo_quality_feedback.py`
- `apps/web/src/features/f16_photo_quality_feedback/Panel.tsx`
- `tests/features/test_f16.py`
- `apps/web/tests/features/f16.test.tsx`
- `apps/api/partsiq/api/f16_photo_quality_feedback.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
