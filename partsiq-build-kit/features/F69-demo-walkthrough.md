# F69 Demo walkthrough

Status: specified, not implemented.

Owning prompt: `prompts/F69-demo-walkthrough.md`.

Behavior: Create 3-minute and 8-minute scripts covering happy path, missing serial, incompatibility, stock split and human review; include recording checklist and captions.

Failure criteria: Do not claim video exists until recorded; use synthetic data; show failure handling and reset; verify links before sending recruiters.

API operations: No independent endpoint

Files:
- `apps/api/partsiq/features/f69_demo_walkthrough.py`
- `apps/web/src/features/f69_demo_walkthrough/Panel.tsx`
- `tests/features/test_f69.py`
- `apps/web/tests/features/f69.test.tsx`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
