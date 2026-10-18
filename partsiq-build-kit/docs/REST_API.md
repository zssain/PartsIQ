# REST API contract

## Transport rules

FastAPI is the only business API. Base prefix is /v1. HTTPS is required outside localhost. JSON requests use Content-Type application/json. Authorization uses a Supabase Bearer token; never use a customer-supplied actor field. Every response carries X-Request-ID. Every mutating request, including DELETE, requires an Idempotency-Key UUID. The key is scoped by actor, method and path; reusing it with different payload returns 409. JSON updates carry expected_revision where specified. A POST returning202 has committed a job/resource but has not completed the background action.

Typed models in spec/contracts.py and spec/api_models.py are canonical. spec/openapi.json expands their fields and nested schemas; spec/endpoints.json declares ownership. No unknown keys are accepted. UUIDs are strings on the wire, Decimal quantities/costs are decimal strings, datetimes are ISO8601UTC and serial/part numbers remain strings. For strict Pydantic models use JSON-aware validation at the HTTP boundary; do not reject valid JSON UUID strings because a Python-only strict validator expects a UUID instance.

GET requests with Query models use validated query parameters, not a JSON body. Repeated comparison part_ids are repeated query parameters. Cursor pagination orders by(created_at, id), uses a base64url encoded typed tuple, and rejects invalid cursors. Cursor validity is not authorization; always apply scope filters. limit defaults25 and caps100. Unknown status/filter values are422. A route response is bounded; large histories are paginated and private details are separate resources.

## Access labels

public means no account. customer means any verified eligible user including an anonymous demo user with an active session where needed. demo means the subject's own active demo session. owner means the enquiry owner or authorized staff via the same scope rule. review means own-session demo reviewer, assigned real reviewer, or admin. reviewer means reviewer/admin listing only its permitted records, plus own-demo context. catalogue_admin means catalogue_admin/admin and never an anonymous demo. admin means server-side admin membership. scoped means derive ownership through the referenced job/export/resource; never authorize merely because the caller knows a UUID.

## Errors

All failures use application/problem+json with Problem fields: type, title, status, code, detail, request_id, retryable.401 means missing/invalid token; 403 means a known disallowed role action; 404 conceals a foreign scoped resource; 409 means stale revision, idempotency conflict, changed catalogue or invalid current state; 413 means size limit; 422 means input/schema validation; 429 means rate limit; 503 means required dependency or live allowance unavailable. Include Retry-After only when retry is appropriate. Never include SQL, provider payloads, secrets or internal file paths. Domain code returns named errors; only route adapters choose HTTP transport.

## Complete operation inventory

| Feature | Method | Path | Request | Response | Access | Success |
|---|---|---|---|---|---|---|
| F02 | GET | /v1/demo/scenarios | None | ScenarioList | demo | 200 |
| F04 | GET | /v1/demo/sessions/{session_id} | None | DemoSession | demo | 200 |
| F05 | POST | /v1/demo/sessions/{session_id}/reset | RevisionOnly | DemoSession | demo | 201 |
| F09 | POST | /v1/enquiries | EnquiryCreate | EnquiryView | customer | 202 |
| F10 | GET | /v1/enquiries/{enquiry_id}/extraction | None | ExtractionView | owner | 200 |
| F11 | POST | /v1/enquiries/{enquiry_id}/messages | MessageCreate | EnquiryView | owner | 202 |
| F12 | GET | /v1/enquiries/{enquiry_id}/messages | PageQuery | MessagePage | owner | 200 |
| F13 | POST | /v1/enquiries/{enquiry_id}/uploads | UploadRequest | UploadTicket | owner | 200 |
| F14 | POST | /v1/attachments/{attachment_id}/confirm-upload | RevisionOnly | JobView | owner | 202 |
| F15 | POST | /v1/enquiries/{enquiry_id}/confirm-nameplate | ConfirmExtraction | EnquiryView | owner | 202 |
| F16 | GET | /v1/attachments/{attachment_id}/quality | None | QualityView | owner | 200 |
| F17 | PATCH | /v1/enquiries/{enquiry_id}/items | ItemsEdit | EnquiryView | owner | 200 |
| F18 | GET | /v1/enquiries/{enquiry_id}/progress | None | ProgressView | owner | 200 |
| F19 | GET | /v1/enquiries | HistoryQuery | EnquiryPage | customer | 200 |
| F20 | GET | /v1/enquiries/{enquiry_id}/items/{item_id}/machine | None | MachineView | owner | 200 |
| F21 | GET | /v1/enquiries/{enquiry_id}/items/{item_id}/mismatch | None | MismatchView | owner | 200 |
| F22 | GET | /v1/enquiries/{enquiry_id}/items/{item_id}/compatibility | None | CompatibilityView | review | 200 |
| F23 | GET | /v1/enquiries/{enquiry_id}/items/{item_id}/match-evidence | None | MatchEvidenceView | review | 200 |
| F24 | GET | /v1/search/capabilities | None | SearchCapabilities | customer | 200 |
| F25 | GET | /v1/enquiries/{enquiry_id}/items/{item_id}/candidates | None | CandidateList | review | 200 |
| F26 | POST | /v1/enquiries/{enquiry_id}/items/{item_id}/choice | CandidateChoice | EnquiryView | owner | 202 |
| F27 | GET | /v1/enquiries/{enquiry_id}/items/{item_id}/explanation | None | ExplanationView | owner | 200 |
| F28 | GET | /v1/enquiries/{enquiry_id}/items/{item_id}/references | None | ReferenceList | owner | 200 |
| F29 | POST | /v1/enquiries/{enquiry_id}/evidence/{evidence_id}/download | RevisionOnly | DownloadTicket | review | 200 |
| F30 | GET | /v1/catalogue/parts/{part_number}/supersession | None | SupersessionView | customer | 200 |
| F31 | GET | /v1/enquiries/{enquiry_id}/items/{item_id}/comparison | ComparisonQuery | CandidateList | review | 200 |
| F32 | GET | /v1/enquiries/{enquiry_id}/items/{item_id}/stock | None | StockView | review | 200 |
| F33 | GET | /v1/enquiries/{enquiry_id}/plan | None | PlanView | review | 200 |
| F34 | GET | /v1/enquiries/{enquiry_id}/transfers | None | TransferView | review | 200 |
| F35 | GET | /v1/enquiries/{enquiry_id}/stock-freshness | None | FreshnessView | review | 200 |
| F36 | GET | /v1/staff/enquiries | InboxQuery | EnquiryPage | reviewer | 200 |
| F37 | GET | /v1/staff/enquiries/{enquiry_id} | None | ReviewView | review | 200 |
| F38 | PATCH | /v1/staff/enquiries/{enquiry_id}/extraction | RevisionRequest | EnquiryView | review | 200 |
| F39 | POST | /v1/staff/enquiries/{enquiry_id}/approve | ApprovalRequest | ApprovalResult | review | 200 |
| F40 | GET | /v1/staff/enquiries/{enquiry_id}/approval-state | None | ApprovalState | review | 200 |
| F41 | POST | /v1/staff/enquiries/{enquiry_id}/notes | NoteCreate | NoteView | review | 201 |
| F42 | PUT | /v1/staff/enquiries/{enquiry_id}/assignment | AssignRequest | AssignmentView | admin | 200 |
| F43 | GET | /v1/staff/enquiries/{enquiry_id}/deadline | None | DeadlineView | review | 200 |
| F44 | POST | /v1/staff/enquiries/{enquiry_id}/summary | RevisionOnly | JobView | review | 202 |
| F45 | PUT | /v1/staff/enquiries/{enquiry_id}/draft | DraftEdit | DraftView | review | 200 |
| F46 | GET | /v1/staff/enquiries/{enquiry_id}/verification | None | VerificationResult | review | 200 |
| F47 | GET | /v1/enquiries/{enquiry_id}/published-reply | None | PublishedView | owner | 200 |
| F49 | GET | /v1/staff/enquiries/{enquiry_id}/audit | PageQuery | AuditPage | review | 200 |
| F50 | GET | /v1/staff/enquiries/{enquiry_id}/workflow | None | WorkflowView | review | 200 |
| F51 | GET | /v1/jobs/{job_id} | None | JobView | scoped | 200 |
| F52 | POST | /v1/jobs/{job_id}/retry | RetryRequest | JobView | scoped | 202 |
| F54 | GET | /v1/me | None | IdentityView | customer | 200 |
| F55 | POST | /v1/machines | MachineSave | SavedMachineView | customer | 201 |
| F56 | POST | /v1/enquiries/{enquiry_id}/repeat | RepeatRequest | EnquiryView | owner | 202 |
| F57 | GET | /v1/catalogue/parts | CatalogueQuery | CataloguePage | customer | 200 |
| F58 | POST | /v1/admin/imports | ImportCreate | ImportView | catalogue_admin | 201 |
| F59 | POST | /v1/admin/imports/{import_id}/publish | PublishRequest | JobView | catalogue_admin | 202 |
| F60 | PATCH | /v1/staff/missing-parts/{item_id} | MissingUpdate | MissingView | review | 200 |
| F61 | POST | /v1/enquiries/{enquiry_id}/exports | ExportRequest | JobView | owner | 202 |
| F62 | POST | /v1/admin/evaluations | EvalRequest | JobView | admin | 202 |
| F63 | GET | /v1/staff/metrics | MetricsQuery | MetricsView | reviewer | 200 |
| F64 | GET | /v1/admin/ai-allowance | None | AllowanceView | admin | 200 |
| F65 | POST | /v1/admin/corrections/{correction_id}/evaluation-case | CurateRequest | CuratedView | admin | 201 |
| F67 | GET | /v1/staff/enquiries/{enquiry_id}/traces | None | TraceView | review | 200 |
| F04 | POST | /v1/demo/sessions | None | DemoSession | demo | 201 |
| F09 | GET | /v1/enquiries/{enquiry_id} | None | EnquiryView | owner | 200 |
| F13 | GET | /v1/enquiries/{enquiry_id}/attachments | None | AttachmentList | owner | 200 |
| F39 | POST | /v1/staff/enquiries/{enquiry_id}/reject | RejectionRequest | ReviewResult | review | 200 |
| F41 | GET | /v1/staff/enquiries/{enquiry_id}/notes | PageQuery | NotePage | review | 200 |
| F44 | GET | /v1/staff/enquiries/{enquiry_id}/summary | None | SummaryView | review | 200 |
| F55 | GET | /v1/machines | PageQuery | MachinePage | customer | 200 |
| F55 | DELETE | /v1/machines/{machine_id} | None | ArchiveResult | customer | 200 |
| F57 | GET | /v1/catalogue/parts/{part_number} | None | CataloguePart | customer | 200 |
| F58 | GET | /v1/admin/imports/{import_id} | None | ImportView | catalogue_admin | 200 |
| F58 | POST | /v1/admin/imports/{import_id}/upload | ImportUpload | UploadTicket | catalogue_admin | 200 |
| F58 | POST | /v1/admin/imports/{import_id}/validate | None | JobView | catalogue_admin | 202 |
| F59 | GET | /v1/admin/catalogue/versions | None | VersionList | catalogue_admin | 200 |
| F60 | GET | /v1/staff/missing-parts | InboxQuery | MissingPage | reviewer | 200 |
| F61 | GET | /v1/exports/{export_id}/download | None | DownloadTicket | owner | 200 |
| F62 | GET | /v1/admin/evaluations/{run_id} | None | EvaluationView | admin | 200 |
| F63 | GET | /v1/admin/analytics/sync | None | AnalyticsSyncView | admin | 200 |
| F64 | PUT | /v1/admin/ai-allowance | AllowanceSet | AllowanceView | admin | 200 |

## Worked request and lifecycle

POST /v1/enquiries uses EnquiryCreate: text, locale, destination_warehouse_id, and optional session_id. It returns EnquiryView with id, revision, status, messages, item_ids, catalogue_version_id and updated_at. The server creates the first message and a durable workflow job in the same transaction. A client then polls GET /v1/enquiries/{enquiry_id}/progress and GET /v1/enquiries/{enquiry_id}. It does not poll Snowflake directly.

If a nameplate is present, the upload endpoint issues a ticket; the browser uploads bytes and confirms that attachment. The worker validates/reads the image and the client confirms the resulting identifiers. Once a verified draft exists, an assigned reviewer reads the staff workspace and posts ApprovalRequest. The API locks/revalidates and commits approval plus recommendation together. If the request has an old revision, it returns 409 and the UI reloads; it never silently approves a new revision.

## Route implementation pattern

Define a separate APIRouter in each owned feature route module. Use Depends for verified actor and typed command dependencies. The handler calls its feature facade exactly once, with path IDs and idempotency context. A facade calls foundation domain functions and returns the declared model. Register the router in api/router.py only after its module exists. No model-generated route, SQL or endpoint name is accepted. Keep responses free from internal notes unless this is an explicitly authorized staff-only model.

## Versioning and contract tests

The backend generates OpenAPI during CI. Compare the completed operation subset during incremental work; the final gate requires all 77 specified operations and their response schemas. TypeScript types/Zod schemas must represent the same fields. Additive fields still require a documented contract update because strict models reject unknown keys. Breaking changes require a new API version or coordinated migration; do not silently change an existing field's type.
