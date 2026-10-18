# F58 Catalogue imports

Status: specified, not implemented.

Owning prompt: `prompts/F58-catalogue-imports.md`.

Behavior: Read CSV UTF-8 or XLSX without evaluating formulas; validate row schema, references, serial overlap, supersession cycles and source evidence; show dry-run report; explicit admin publish. Stage a version in Snowflake, validate all relationships explicitly and only then activate a validated PostgreSQL serving snapshot.

Failure criteria: Invalid batch changes no published data; file with macros/formulas rejected; 50000-row and 10MiB limits enforced; public demo cannot publish.

API operations: f58_stage_import, f58_read_import, f58_sign_import_upload, f58_validate_import

Files:
- `apps/api/partsiq/features/f58_catalogue_imports.py`
- `apps/web/src/features/f58_catalogue_imports/Panel.tsx`
- `tests/features/test_f58.py`
- `apps/web/tests/features/f58.test.tsx`
- `apps/api/partsiq/api/f58_catalogue_imports.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
