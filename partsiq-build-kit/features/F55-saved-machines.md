# F55 Saved machines

Status: specified, not implemented.

Owning prompt: `prompts/F55-saved-machines.md`.

Behavior: Save confirmed model and serial with user label; list own active entries; archive entry; prefill a new enquiry but re-identify against current catalogue.

Failure criteria: Duplicate label permitted with distinct ID; foreign ID denied; stale configuration never reused as authoritative.

API operations: f55_save, f55_list_owned, f55_archive

Files:
- `apps/api/partsiq/features/f55_saved_machines.py`
- `apps/web/src/features/f55_saved_machines/Panel.tsx`
- `tests/features/test_f55.py`
- `apps/web/tests/features/f55.test.tsx`
- `apps/api/partsiq/api/f55_saved_machines.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
