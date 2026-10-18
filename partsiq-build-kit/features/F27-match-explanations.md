# F27 Match explanations

Status: specified, not implemented.

Owning prompt: `prompts/F27-match-explanations.md`.

Behavior: Show actual alias, machine configuration, supersession chain and fitment reference; derive explanations from search evidence rather than invented model prose.

Failure criteria: Absent evidence shown as unavailable; user HTML is escaped; scores never labelled calibrated probability.

API operations: f27_explain_selection

Files:
- `apps/api/partsiq/features/f27_match_explanations.py`
- `apps/web/src/features/f27_match_explanations/Panel.tsx`
- `tests/features/test_f27.py`
- `apps/web/tests/features/f27.test.tsx`
- `apps/api/partsiq/api/f27_match_explanations.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
