# Security and permission design

## Trust boundaries

Browser requests are untrusted. Supabase tokens are verified for issuer, audience, signature, algorithm and expiry. Role membership is loaded server-side. Customer text, OCR text, imported documents and model replies are data, not instructions to privileged code. The AI API has no tools for writes or approval. Snowflake queries use bound values and fixed identifiers.

## Access matrix

| Resource | Customer or own demo | Assigned reviewer | Catalogue admin | Admin |
|---|---|---|---|---|
| Own enquiry/messages/progress | Read and allowed input changes | Assigned real enquiry | No automatic access | Operational access |
| Candidates and full evidence | Own demo reviewer only | Assigned enquiry | No automatic access | Operational access |
| Approve/edit/reject | Own demo reviewer only | Assigned enquiry | No automatic access | Operational access |
| Internal notes/audit | Own demo reviewer only | Assigned enquiry | No automatic access | Operational access |
| Published catalogue | Read active data | Read | Stage/validate/publish | Stage/validate/publish |
| Assignments | No | No | No | Manage |
| AI allowance/evaluation curation | No | No | No | Manage |
| Snowflake aggregate reports | No | No | No | Read |

An invited user can hold multiple roles explicitly. A catalogue admin is not implicitly a reviewer. API access labels are defined in REST_API.md. PostgreSQL runtime groups are technical permissions and must not be mistaken for human application roles.

## Database and file controls

Use RLS on every application table. anon/authenticated cannot access application tables directly except explicitly defined Storage policies. API uses a least-privilege LOGIN role with only the partsiq_api group; worker code selects purpose-specific pools with workflow/search/worker/catalogue groups. Do not use an owner/service-role database connection for ordinary business queries. Trusted jobs authorize by their persisted enquiry/revision and do not accept arbitrary user-selected table IDs.

Storage buckets are private. Use server-chosen object keys and short-lived signed URLs. Check actual image bytes and decoded size, strip metadata, and reject path traversal. Evidence/export download checks assignment or ownership at issuance; already issued URLs have a bounded validity window. PDF rendering blocks external network requests.

## Abuse and reliability

Apply per-identity/IP request limits, upload size limits and bounded pagination. Redis limiter failure denies new rate-limited work instead of removing protection. Idempotency keys bind actor, method, path and payload hash. Worker leases prevent expired results overwriting new revisions. API CORS allows only explicit frontend origins. CSP and output escaping limit injected markup. Never display unescaped AI/customer text as HTML.

Audit rows are immutable to runtime roles; schema owners retain administrative capabilities, so describe this honestly. Store minimal before/after fields and redact secrets. Role changes, assignment, approval, publication, imports and allowance changes are auditable. Real retention requires a client decision before onboarding; demo access expires after24hours, with cleanup and minimal audit retention documented separately.
