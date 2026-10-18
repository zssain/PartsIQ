# F20 Machine identification

Status: specified, not implemented.

Owning prompt: `prompts/F20-machine-identification.md`.

Behavior: Preserve identify_machine logic for model, serial and rating; return resolved configuration or explicit missing/ambiguous status; normalize numeric serial only after preserving input.

Failure criteria: Boundary serials match exactly one configuration; overlapping ranges fail Snowflake publication validation and PostgreSQL serving-cache insertion; conflicting hints never silently override.

API operations: f20_identify_machine

Files:
- `apps/api/partsiq/features/f20_machine_identification.py`
- `apps/web/src/features/f20_machine_identification/Panel.tsx`
- `tests/features/test_f20.py`
- `apps/web/tests/features/f20.test.tsx`
- `apps/api/partsiq/api/f20_machine_identification.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
