# F21 Machine mismatch detection

Status: specified, not implemented.

Owning prompt: `prompts/F21-machine-mismatch-detection.md`.

Behavior: Compare model and serial together; return mismatch reason with safe next question; prevent retrieval while identity unresolved.

Failure criteria: Valid serial of a different model does not match requested model; nonnumeric serial handled without crashing.

API operations: f21_check_hints

Files:
- `apps/api/partsiq/features/f21_machine_mismatch_detection.py`
- `apps/web/src/features/f21_machine_mismatch_detection/Panel.tsx`
- `tests/features/test_f21.py`
- `apps/web/tests/features/f21.test.tsx`
- `apps/api/partsiq/api/f21_machine_mismatch_detection.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
