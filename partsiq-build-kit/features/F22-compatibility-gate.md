# F22 Compatibility gate

Status: specified, not implemented.

Owning prompt: `prompts/F22-compatibility-gate.md`.

Behavior: Fetch authoritative fitment set first; rank only members; carry source_reference and catalogue version through every candidate.

Failure criteria: A perfect lexical match outside fitment is absent; empty fitment returns unavailable; blank provenance cannot be published.

API operations: f22_compatible_set

Files:
- `apps/api/partsiq/features/f22_compatibility_gate.py`
- `apps/web/src/features/f22_compatibility_gate/Panel.tsx`
- `tests/features/test_f22.py`
- `apps/web/tests/features/f22.test.tsx`
- `apps/api/partsiq/api/f22_compatibility_gate.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
