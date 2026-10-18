# F62 Labelled evaluations

Status: specified, not implemented.

Owning prompt: `prompts/F62-labelled-evaluations.md`.

Behavior: Include four demos plus Arabic, typo, serial-boundary, ambiguity, stock and injection cases; record expected compatible set and clarification outcome; run deterministic suite without API calls.

Failure criteria: No self-reported model confidence as accuracy; evaluation fixture disjoint from examples used in prompts; failures keep actual output.

API operations: f62_enqueue_run, f62_read_run

Files:
- `apps/api/partsiq/features/f62_labelled_evaluations.py`
- `apps/web/src/features/f62_labelled_evaluations/Panel.tsx`
- `tests/features/test_f62.py`
- `apps/web/tests/features/f62.test.tsx`
- `apps/api/partsiq/api/f62_labelled_evaluations.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
