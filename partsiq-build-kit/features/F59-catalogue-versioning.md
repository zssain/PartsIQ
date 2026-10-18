# F59 Catalogue versioning

Status: specified, not implemented.

Owning prompt: `prompts/F59-catalogue-versioning.md`.

Behavior: Store immutable versioned catalogue records in Snowflake; verify record counts and canonical SHA256; stage the PostgreSQL serving snapshot; atomically switch the active version in a PostgreSQL transaction; retain published historical records; reconcile partial remote writes.

Failure criteria: Two publishers cannot leave two active versions; failed publish rolls back; old approval retains immutable evidence snapshot.

API operations: f59_request_publish, f59_list_versions

Files:
- `apps/api/partsiq/features/f59_catalogue_versioning.py`
- `apps/web/src/features/f59_catalogue_versioning/Panel.tsx`
- `tests/features/test_f59.py`
- `apps/web/tests/features/f59.test.tsx`
- `apps/api/partsiq/api/f59_catalogue_versioning.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
