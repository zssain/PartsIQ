# F28 Compatibility references

Status: specified, not implemented.

Owning prompt: `prompts/F28-compatibility-references.md`.

Behavior: Resolve source_reference to version-specific document and page; retain citation with every candidate and approval snapshot.

Failure criteria: Missing source file blocks evidence viewer and flags review; mismatched version fails verification.

API operations: f28_list_references

Files:
- `apps/api/partsiq/features/f28_compatibility_references.py`
- `apps/web/src/features/f28_compatibility_references/Panel.tsx`
- `tests/features/test_f28.py`
- `apps/web/tests/features/f28.test.tsx`
- `apps/api/partsiq/api/f28_compatibility_references.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
