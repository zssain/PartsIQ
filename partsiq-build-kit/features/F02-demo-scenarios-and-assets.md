# F02 Demo scenarios and assets

Status: specified, not implemented.

Owning prompt: `prompts/F02-demo-scenarios-and-assets.md`.

Behavior: Seed four deterministic scenarios: mixed-language photo, missing serial, incompatible part, local shortage; derive identifiers from seed 42; validate expected outcomes against generated records.

Failure criteria: Reject a scenario whose expected part lacks compatibility; reject stock claims not supported by fixture quantities.

API operations: f02_list_scenarios

Files:
- `apps/api/partsiq/features/f02_demo_scenarios_and_assets.py`
- `apps/web/src/features/f02_demo_scenarios_and_assets/Panel.tsx`
- `tests/features/test_f02.py`
- `apps/web/tests/features/f02.test.tsx`
- `apps/api/partsiq/api/f02_demo_scenarios_and_assets.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
