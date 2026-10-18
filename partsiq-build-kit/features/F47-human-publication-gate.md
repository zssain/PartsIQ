# F47 Human publication gate

Status: specified, not implemented.

Owning prompt: `prompts/F47-human-publication-gate.md`.

Behavior: Only approval service inserts recommendation messages; lock enquiry and recheck role, revision and verification; unique publication index prevents duplicates.

Failure criteria: No background job write tool can publish; database rejects recommendation lacking matching approved decision.

API operations: f47_read_approved

Files:
- `apps/api/partsiq/features/f47_human_publication_gate.py`
- `apps/web/src/features/f47_human_publication_gate/Panel.tsx`
- `tests/features/test_f47.py`
- `apps/web/tests/features/f47.test.tsx`
- `apps/api/partsiq/api/f47_human_publication_gate.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
