# F37 Review workspace

Status: specified, not implemented.

Owning prompt: `prompts/F37-review-workspace.md`.

Behavior: Assemble current extraction, items, candidates, evidence, stock, draft and timeline; show verification failures; separate staff-only notes from customer messages.

Failure criteria: Missing panels show explicit empty states; stale revision disables approval; unassigned reviewer receives 404.

API operations: f37_get_workspace

Files:
- `apps/api/partsiq/features/f37_review_workspace.py`
- `apps/web/src/features/f37_review_workspace/Panel.tsx`
- `tests/features/test_f37.py`
- `apps/web/tests/features/f37.test.tsx`
- `apps/api/partsiq/api/f37_review_workspace.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
