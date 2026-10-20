# Workspace API contracts (additive /v1 surface, ADR 0002)

The authoritative schemas are the FastAPI handlers in `apps/api/partsiq/api/workspace_api.py`
and their typed client in `apps/web/lib/workspace.ts` (OpenAPI at `/openapi.json`).
Existing /v1 contracts (F02–F67) are unchanged except the additive fields noted below.

## Conventions

| Topic | Rule |
| --- | --- |
| Authentication | `Authorization: Bearer <Supabase access token>` (invited account) **or** `X-Demo-Token` (public demo). A bearer never falls back to demo identity. Neither header → 401. |
| Scope | Resources outside the caller's workspace or role scope → **404** (no existence leak). Missing capability → **403**. |
| Mutations | `Idempotency-Key: <uuid>` is required. Same key + same body replays the stored result; same key + different body → **409 IDEMPOTENCY_MISMATCH**. |
| Concurrency | Enquiry state changes carry `expected_revision`. A stale value → **409 STALE_REVISION**. Optional `expected_state_version` on run commands → 409 CONFLICT. |
| Errors | RFC 9457 Problem with `code`, `detail` and `request_id`. 422 invalid input, 429 limits/quota, 503 unavailable dependency, `CREDIT_UNAVAILABLE` for an unavailable live allowance. No internal detail is returned. |
| Audit | Every decision, run command, assignment, role change, import and publish appends an audit event in the same critical section. |

## Identity

`GET /v1/me` → `IdentityView`. Additive fields: `kind` (demo|account), `display_name`, `email`,
`capabilities[]`, `demo_session_generation`, `demo_expires_at`, `data_source`, `ai_mode`,
`live_available`, `collaboration_enabled`.

## Enquiries and runs

| Method & path | Capability | Body | Response | Notes |
| --- | --- | --- | --- | --- |
| `POST /v1/enquiries?mode=guided\|collaboration[&defer=true]` | enquiry.create | `EnquiryCreate` | 202 `EnquiryView` | The mode is fixed for the run. `defer` commits without starting a run (attach a photo, then start). |
| `GET /v1/enquiries/{id}/detail` | enquiry.read_own | — | composed detail | Reviewer-only fields (draft, step details) appear only for review scope. |
| `GET /v1/workspace/enquiries?scope=own\|review&status&q&mode&assigned=me\|none&overdue&cursor&limit` | read_own / review.queue | — | page | Offset cursor; `total` is scope-limited. |
| `GET /v1/workspace/dashboard` | any | — | counts | Review counts only with review.queue. |
| `POST /v1/enquiries/{id}/runs` | run control in scope | `{mode, expected_revision}` | 202 Run | 409 while a non-blocked run is active (cancel first; history kept). |
| `GET /v1/enquiries/{id}/runs` | read | — | Run[] | Newest first, including superseded runs. |
| `GET /v1/runs/{id}` | read | — | Run | Limits, usage (tokens `null` = not measured), roster, pending, `available_actions`. |
| `GET /v1/runs/{id}/events?after=<seq>&limit` | read | — | `{items, next_after, run}` | Gap-free `seq` per run; clients de-duplicate by seq. |
| `POST /v1/runs/{id}/commands` | owner, or `run.control_assigned` in scope | `{type, expected_revision, expected_state_version?, payload}` | 202 `{id, result, replayed, run}` | Types: pause, resume, cancel, instruct `{text}`, answer `{text}`, confirm_nameplate `{model_text, serial_text}`, resolve_delegation `{decision: approve\|deny}`, fixture_replay. |
| `GET /v1/enquiries/{id}/pending` | read | — | open pending actions | clarification / delegation_consent / nameplate_confirmation. |
| `POST /v1/enquiries/{id}/attachments` | owner | image bytes (`image/jpeg\|png\|webp`) | 201 | Type allowlist, magic bytes, ≤ MAX_UPLOAD_BYTES, decoded pixels ≤ MAX_IMAGE_PIXELS. After processing has started, this creates a new revision. |
| `POST /v1/enquiries/{id}/attachments/sample` | owner | — | 201 | Attaches the committed synthetic nameplate (server-read file). |

Command semantics: **pause** stops new dispatch. A step already in flight finishes
("pausing"), and its result stays unpublished. **resume** re-checks catalogue version and
live availability, then continues from saved state without repeating steps. **cancel** fences
the run: late results are discarded and recorded, and history is kept. Cancelling never
deletes the enquiry. **instruct** is untrusted input; factual content is flagged and must be
sent as a message (new revision). **answer** / **confirm_nameplate** create a new revision and
run. **resolve_delegation** continues the same run.

## Review

`ReviewView.draft_id` (additive) — `POST /v1/staff/enquiries/{id}/approve` must carry it with
`expected_revision`. Approval refreshes stock and re-runs verification. A failure, a changed
draft, a superseded or cancelled run, or a retired catalogue version → 409. It publishes at
most once per revision; replays return `already_applied: true`.
`GET /v1/staff/enquiries/{id}/detail` → composed review read (evidence, notes, reviewers,
decisions, history).

## Catalogue, imports, administration

| Method & path | Capability |
| --- | --- |
| `GET /v1/catalogue/search?q&category&model&cursor&limit` | read (active version of caller's workspace) |
| `GET /v1/catalogue/parts/{number}/detail` | read — aliases, fitment rows with sources, supersession both ways, stock |
| `POST /v1/admin/imports` → `POST …/{id}/upload` (ticket) → `PUT …/{id}/content` (text/csv) → `POST …/{id}/validate` → `GET …/{id}/preview` → `POST …/{id}/publish {content_sha256, expected_active_version_id}` | catalogue.import / catalogue.publish. CSV only; formula-like cells rejected; dry run merges onto the active version and runs `validate_snapshot` (schema, references, serial overlap, supersession graph); publish is compare-and-set. |
| `GET /v1/admin/imports`, `GET /v1/admin/catalogue/versions` | catalogue.import / catalogue.browse |
| `GET /v1/admin/members`, `POST /v1/admin/members/invite`, `PUT /v1/admin/members/{id}/roles {roles, expected_version}` | admin.users. Accounts: Supabase admin API. Demo: synthetic personas. Cannot remove your own admin role. |
| `GET /v1/admin/audit?action&entity&actor_id&cursor&limit` | audit.read (read-only) |
| `GET /v1/admin/jobs?status` | jobs.read — runs + jobs, attempts, error category, dependency states |
| `GET /v1/admin/analytics` | analytics.read — unmeasured values are `null` with a note |
| `GET /v1/admin/evaluations`, `POST /v1/admin/evaluations {suite:"deterministic"}` | evaluation.run — real pipeline over `evals/cases.json` |
| `GET /v1/admin/corrections`, `POST …/{id}/reviewed` | evaluation.run |
| `GET /v1/workspace/status`, `GET /v1/warehouses`, `GET /v1/machines/{id}/check` | any verified caller |
