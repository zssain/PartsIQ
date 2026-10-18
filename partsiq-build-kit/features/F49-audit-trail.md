# F49 Audit trail

Status: specified, not implemented.

Owning prompt: `prompts/F49-audit-trail.md`.

Behavior: Append actor, request, entity, revision and minimal before/after metadata for AI suggestions and human changes; redact secrets and full sensitive payloads.

Failure criteria: Application UPDATE, DELETE, TRUNCATE fail; audit write failure rolls back approval; database-owner powers documented honestly.

API operations: f49_list_events

Files:
- `apps/api/partsiq/features/f49_audit_trail.py`
- `apps/web/src/features/f49_audit_trail/Panel.tsx`
- `tests/features/test_f49.py`
- `apps/web/tests/features/f49.test.tsx`
- `apps/api/partsiq/api/f49_audit_trail.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
