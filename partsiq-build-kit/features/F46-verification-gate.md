# F46 Verification gate

Status: specified, not implemented.

Owning prompt: `prompts/F46-verification-gate.md`.

Behavior: Check item/configuration/candidate membership, provenance, catalogue version, selected quantities and allocation bounds; compute canonical fact hash; store named rule results.

Failure criteria: Unknown part, incompatible part, stale catalogue, oversold plan and hidden extra item each fail a specific rule.

API operations: f46_read_current

Files:
- `apps/api/partsiq/features/f46_verification_gate.py`
- `apps/web/src/features/f46_verification_gate/Panel.tsx`
- `tests/features/test_f46.py`
- `apps/web/tests/features/f46.test.tsx`
- `apps/api/partsiq/api/f46_verification_gate.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
