# F65 Correction feedback

Status: specified, not implemented.

Owning prompt: `prompts/F65-correction-feedback.md`.

Behavior: List authorized before/after corrections; let admin curate anonymized labelled eval cases; record reviewer and source revision; never auto-train on unreviewed edits.

Failure criteria: Private text excluded from exported fixtures; duplicate case source detected; unreviewed correction cannot become ground truth.

API operations: f65_curate_correction

Files:
- `apps/api/partsiq/features/f65_correction_feedback.py`
- `apps/web/src/features/f65_correction_feedback/Panel.tsx`
- `tests/features/test_f65.py`
- `apps/web/tests/features/f65.test.tsx`
- `apps/api/partsiq/api/f65_correction_feedback.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
