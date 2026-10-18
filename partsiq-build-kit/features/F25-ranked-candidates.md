# F25 Ranked candidates

Status: specified, not implemented.

Owning prompt: `prompts/F25-ranked-candidates.md`.

Behavior: Return top candidates with lexical/semantic evidence and deterministic tie order; compute runner-up margin before applying response limit.

Failure criteria: Limit one still reports ambiguity; empty set returns no candidate; NaN scores rejected.

API operations: f25_rank_candidates

Files:
- `apps/api/partsiq/features/f25_ranked_candidates.py`
- `apps/web/src/features/f25_ranked_candidates/Panel.tsx`
- `tests/features/test_f25.py`
- `apps/web/tests/features/f25.test.tsx`
- `apps/api/partsiq/api/f25_ranked_candidates.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
