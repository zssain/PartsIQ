# ADR 0002: Workspace runtime, agent collaboration, run control and account access

Status: accepted (2026-10-20). Extends ADR 0001 (LangGraph remains the guided engine).

## Context

The deployed app had a fixed demo journey (any text produced the same part), staff/admin
ports that returned 503 because no store was wired, no real account sign-in, and no
agent-to-agent mode. The same rules (compatibility, verification, approval) had to back two
execution modes, three experiences and two entry paths.

## Decision

1. **One runtime behind the existing ports.** `partsiq.workspace.WorkspaceService` implements
   the intake store (F09–F19), the staff review source (F36–F50, F67) and the ops/admin ports
   (F55–F65). Feature facades and their contracts are unchanged; new composed reads and run
   endpoints are additive (`docs/API_WORKSPACE.md`). No second API or catalogue implementation.
2. **Workspaces isolate state by construction.** Invited accounts share one account workspace.
   Each public demo session generation gets its own disposable workspace (own catalogue copy,
   enquiries, runs, audit, personas). A foreign id is simply absent, so it is 404. Reset or
   expiry abandons the workspace and fences its runs.
3. **One shared pipeline.** `workspace/steps.py` + `domain.py` adapt the characterised services
   (identification, compatible-only search with explicit successor fitment, ambiguity thresholds,
   fulfilment over approved routes, seven-rule verification, code-owned renderer). Both modes
   call the same steps.
4. **Guided mode** compiles the LangGraph graph with `interrupt_before` every node. The runner
   dispatches one node per call, so pause and cancel apply at a safe boundary. Routing is still
   `transitions.next_step` (three edges were added — SEARCH→CLARIFY, PLAN→CLARIFY, INTAKE→CONFIRM —
   and a `needs_staff` phase).
5. **Collaboration mode** is a code-owned controller (`workspace/collaboration.py`). The four
   specialists (intake, nameplate, parts, reply) only propose actions. The controller enforces
   the routing matrix and message kinds, a per-agent tool allowlist with id-only arguments,
   proposal compatibility checks, "ready for review only after verification passed",
   repeated-exchange and loop detection, size bounds and run limits. Consent-gated delegations
   create pending actions. Every accepted or rejected action is persisted as an ordered
   exchange. No broadcast, no write tools, and hidden reasoning is never stored.
6. **Server-enforced controls.** `POST /v1/runs/{id}/commands`
   (pause/resume/cancel/instruct/answer/confirm_nameplate/resolve_delegation/fixture_replay)
   requires an Idempotency-Key and the expected enquiry revision. Each step is computed on a
   copy and committed only while the run's fence holds. Cancel, supersede and reset bump the
   fence, so a late result is discarded and recorded. Factual input (answers, confirmations,
   photos, messages) always creates a new revision and a new run; earlier runs stay as history.
7. **Execution source is fixed per run.** A run is `live` only when AI_MODE=live, a key and
   model are configured, and a confirmed, unexpired allowance exists. Otherwise it is `fixture`.
   A live run that loses its provider or allowance blocks. Fixture replay is a separate,
   labelled run. There is no paid fallback.
8. **Accounts and capabilities.** Bearer tokens are verified against the Supabase JWKS
   (RS256/ES256), or HS256 only when the server holds the legacy secret. Roles come from the
   Auth admin API (`app_metadata.partsiq_roles`, writable only with the service role) or from
   `staff_roles` when the database is wired. `auth/actors.py` maps roles to capabilities. Demo
   actors carry no roles, but they hold sandbox capabilities scoped to their own workspace.
   Real-only capabilities (the AI allowance) are never granted to demo actors. Navigation is
   built from `/v1/me` capabilities, and every endpoint re-checks them.
9. **Contracts.** `ReviewView.draft_id` and the `IdentityView` capability fields are additive.
   Approval must name the exact draft (409 on change).

## Persistence (updated 2026-10-20)

**Account workspace: PostgreSQL is the source of truth when `DATABASE_URL_API` is set.**
`partsiq/persistence/workspace_store.py` loads every aggregate at startup. The workspace lock
(`PersistingLock`) is the unit of work. When a critical section exits cleanly, changed rows are
flushed in one batched transaction **before** the caller reports success. If the section raised
or the flush failed, the cache is reloaded from PostgreSQL. Database mode never falls back to
memory: if a required table is missing or another API instance holds the writer lock (advisory
lock 710071), startup fails.

- LangGraph uses `AsyncPostgresSaver` with a contract-aware serializer. Each guided step
  commits its result *inside* the node, before the checkpoint that advances past it, and a
  replay skips a step whose `step_completed` exchange already exists. A crash therefore
  never repeats committed work.
- Interrupted runs resume on startup (`resume_interrupted`).
- Demo sandboxes stay in memory on purpose: anonymous, per-session and disposable.
- Additive migration `20261020000200_workspace_persistence.sql` holds the runtime state the
  003 schema did not cover. No applied migration was edited.

**Background work.** `partsiq/jobs/live.py` implements the existing worker ports over the
`jobs` table:

- `SKIP LOCKED` claims with a fresh fencing token, renewed leases, and completion fenced on
  token, revision and demo generation.
- Redis is only a wake-up channel. A lost push or a Redis outage is covered by the sweeper and
  by direct PostgreSQL polling.
- The API stays the single writer of the account workspace. The worker records its result on
  the job row and the API applies it. For a nameplate, the guided step awaits the reading
  outside the workspace lock, with a bound. Jobs are deduplicated per attachment or revision.
- Nameplate photos and PDFs live in private Storage buckets; downloads are 60-second signed
  URLs.

**AI allowance.** In database mode `ai/ledger_pg.py` replaces the in-memory ledger. One atomic
`UPDATE … WHERE reserved + consumed + estimate <= cap` per reservation means concurrent
processes cannot exceed the confirmed cap, and recorded spend survives a restart.

**Evidence:**

- `apps/api/tests/integration/restart_recovery.py`: 20/20 on a disposable Supabase.
- `apps/api/tests/integration/worker_e2e.py`: 24/24 against the dev Supabase with local Redis,
  including worker SIGKILL mid-export and a Redis outage.
- `tests/integration/*`: RLS, budget races and append-only checks in CI on `supabase/postgres`.

**Known limits:**

- Exactly one API instance per database (the writer lock).
- Latency is dominated by the database round trip. The owner's project is in Tokyo and EC2 in
  Mumbai: a fixture guided run took 17.2 s from a client about 235 ms away.

## Consequences

The public demo now exercises real rules and both modes without credentials. Real accounts
work wherever Supabase Auth is configured. The legacy `FixtureJourneyStore` remains importable
for its contract tests but no longer serves traffic. Rollback is to revert the implementation
commits. No applied migration was edited, and the `20261020000200` migration is additive, so
the old code ignores its new columns.
