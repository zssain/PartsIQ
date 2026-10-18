# F40 Approval invalidation

Status: specified, not implemented.

Owning prompt: `prompts/F40-approval-invalidation.md`.

Behavior: Bind approval to revision and verified fact hash; any identity, quantity, selection or catalogue-sensitive change requires new draft and approval.

Failure criteria: Old approval cannot authorize new revision; late workflow update cannot overwrite approved current state.

API operations: f40_read_binding

Files:
- `apps/api/partsiq/features/f40_approval_invalidation.py`
- `apps/web/src/features/f40_approval_invalidation/Panel.tsx`
- `tests/features/test_f40.py`
- `apps/web/tests/features/f40.test.tsx`
- `apps/api/partsiq/api/f40_approval_invalidation.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
