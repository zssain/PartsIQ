# F50 Durable workflows

Status: specified, not implemented.

Owning prompt: `prompts/F50-durable-workflows.md`.

Behavior: Persist workflow_runs and workflow_step_results in PostgreSQL; run a fixed Python transition table with durable jobs; serialize each enquiry and fence completion by revision and lease token; recover after restart without LangGraph.

Failure criteria: Duplicate jobs cannot repeat publication; stale revisions are discarded; interrupted steps resume from committed results; no LLM chooses the next step.

API operations: f50_inspect_run

Files:
- `apps/api/partsiq/features/f50_durable_workflows.py`
- `apps/web/src/features/f50_durable_workflows/Panel.tsx`
- `tests/features/test_f50.py`
- `apps/web/tests/features/f50.test.tsx`
- `apps/api/partsiq/api/f50_durable_workflows.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
