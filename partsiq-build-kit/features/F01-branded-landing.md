# F01 Branded landing

Status: specified, not implemented.

Owning prompt: `prompts/F01-branded-landing.md`.

Behavior: Explain the enquiry-to-approval journey; show synthetic-demo notice; expose Start demo and architecture links; display the supplied bilingual logo without stretching.

Failure criteria: Missing repository link hides that action; logo has meaningful alternative text; no affiliation claim.

API operations: No independent endpoint

Files:
- `apps/api/partsiq/features/f01_branded_landing.py`
- `apps/web/src/features/f01_branded_landing/Panel.tsx`
- `tests/features/test_f01.py`
- `apps/web/tests/features/f01.test.tsx`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
