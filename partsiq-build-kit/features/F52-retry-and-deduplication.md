# F52 Retry and deduplication

Status: specified, not implemented.

Owning prompt: `prompts/F52-retry-and-deduplication.md`.

Behavior: Claim with FOR UPDATE SKIP LOCKED; assign lease token; heartbeat; retry transient errors with backoff up to max attempts; fence final writes by lease token.

Failure criteria: Expired worker cannot commit; permanent validation failure not retried; provider timeout marked uncertain and budget held conservatively.

API operations: f52_retry_failed

Files:
- `apps/api/partsiq/features/f52_retry_and_deduplication.py`
- `apps/web/src/features/f52_retry_and_deduplication/Panel.tsx`
- `tests/features/test_f52.py`
- `apps/web/tests/features/f52.test.tsx`
- `apps/api/partsiq/api/f52_retry_and_deduplication.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
