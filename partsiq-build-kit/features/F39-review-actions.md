# F39 Review actions

Status: specified, not implemented.

Owning prompt: `prompts/F39-review-actions.md`.

Behavior: Approve only verified current draft; edit prose through controlled schema then reverify; reject with reason; record actor and idempotency key.

Failure criteria: Double-click publishes once; concurrent edit defeats stale approval; failed verification blocks publication.

API operations: f39_approve, f39_reject

Files:
- `apps/api/partsiq/features/f39_review_actions.py`
- `apps/web/src/features/f39_review_actions/Panel.tsx`
- `tests/features/test_f39.py`
- `apps/web/tests/features/f39.test.tsx`
- `apps/api/partsiq/api/f39_review_actions.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
