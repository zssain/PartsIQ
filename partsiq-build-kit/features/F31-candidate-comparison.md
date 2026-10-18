# F31 Candidate comparison

Status: specified, not implemented.

Owning prompt: `prompts/F31-candidate-comparison.md`.

Behavior: Compare two or three candidates from the same item/revision; show number, names, evidence and warehouse availability; selecting a candidate sends its ID, not browser-authored facts.

Failure criteria: Foreign candidate or stale revision rejected; missing attribute shown as unavailable; keyboard navigation works.

API operations: f31_compare_candidates

Files:
- `apps/api/partsiq/features/f31_candidate_comparison.py`
- `apps/web/src/features/f31_candidate_comparison/Panel.tsx`
- `tests/features/test_f31.py`
- `apps/web/tests/features/f31.test.tsx`
- `apps/api/partsiq/api/f31_candidate_comparison.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
