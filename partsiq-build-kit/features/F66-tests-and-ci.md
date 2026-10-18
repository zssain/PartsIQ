# F66 Tests and CI

Status: specified, not implemented.

Owning prompt: `prompts/F66-tests-and-ci.md`.

Behavior: Run service-isolated Python tests, frontend checks, RLS integration and deterministic evals; build images; require explicit environment approval for deployment; pin action SHAs.

Failure criteria: No prod DB in tests; no secret available to untrusted fork jobs; failed gate blocks deployment.

API operations: No independent endpoint

Files:
- `apps/api/partsiq/features/f66_tests_and_ci.py`
- `tests/features/test_f66.py`
- `apps/web/tests/features/f66.test.tsx`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
