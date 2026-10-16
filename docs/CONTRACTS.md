# Contract rules

`spec/contracts.py` is the exact common Pydantic contract source copied by prompt 01. Use model_validate_json for wire JSON; strict Python validation otherwise. Decimal quantities are serialized as decimal strings, UUIDs as canonical strings, timestamps as UTC ISO8601. Reject extra fields.

Feature-specific request/result fields are declared in each F prompt. Define their BaseModel classes in the named feature implementation file, inheriting common Contract. Python optional fields without defaults remain required nullable fields. TypeScript equivalents use the same field names and explicit null. Each UI component uses the concrete request/result props printed in its feature prompt. No generic feature-ID token is left for the implementation agent to guess.

CandidateView: item_id UUID, revision integer, part_id integer, part_number string, name_en string, name_ar string, score number, reasons string array, source_reference string, evidence_id UUID, stock StockEvidence array. ComparisonRow: field string, values array of string or null. PartView: id integer, part_number string, name_en string, name_ar string, category string, is_active boolean, current_part_id integer or null. ImportErrorView: row_number integer, column string, code string, message string.

WorkflowHandlers is a dataclass with `intake`, `identify`, `search`, `choose`, `plan`, `draft`, `verify` asynchronous callables taking EnquiryState and returning EnquiryState. Blocking states are graph interrupts, not executable specialist functions. Production startup fails readiness until every required handler is registered. Test doubles are injected only by tests.

Public error JSON: `{"error":{"code":"STALE_REVISION","message":"Reload the enquiry and review the current revision.","request_id":"00000000-0000-4000-8000-000000000001"}}`. 400 malformed request; 401 unauthenticated; 403 forbidden role; 404 unavailable/foreign resource; 409 stale/conflicting action; 413 size limit; 415 unsupported content; 422 field validation; 429 quota; 503 dependency unavailable. Never include stack traces or credentials.

Pagination: opaque base64url JSON containing created_at and id, validated before SQL binding; limit 1 through 100 with default20. Cursor is not authorization. Idempotent writes use UUID Idempotency-Key and compare canonical payload hash. Same key/different input returns409. Request validation precedes any provider call.

Legacy SearchService request/response models remain in services/search/app/schemas.py. Add catalogue_version_id and per-item correlation without renaming legacy fields. The adapter translates common contracts into those models. Do not duplicate search domain types in gateway.

Specialized supplementary routes and files are listed in each feature prompt. Use idempotency_records for session reset,notes,saved-machine writes,assignment and catalogue publication where no domain-specific key exists. A reservation response is stored atomically with business change; abandoned request rows have response NULL and may only be resumed under row lock.
