# F35 Stock freshness

Status: specified, not implemented.

Owning prompt: `prompts/F35-stock-freshness.md`.

Behavior: Compare stock timestamp with configurable freshness limit; mark stale data in review; re-read current stock during approval; invalidate plan when allocation no longer possible.

Failure criteria: Future timestamp flagged; changed stock returns 409 and reruns planning; stale stock never becomes a delivery guarantee.

API operations: f35_check_freshness

Files:
- `apps/api/partsiq/features/f35_stock_freshness.py`
- `apps/web/src/features/f35_stock_freshness/Panel.tsx`
- `tests/features/test_f35.py`
- `apps/web/tests/features/f35.test.tsx`
- `apps/api/partsiq/api/f35_stock_freshness.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
