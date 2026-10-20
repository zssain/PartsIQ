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

## Persistence (honest scope)

The runtime holds operational state in process memory in the current deployment, and
LangGraph checkpoints use InMemorySaver. The durable schema for runs, exchanges, commands and
pending actions is the additive migration `20261020000100_agent_collaboration.sql`, validated
against PostgreSQL 16. A PostgreSQL adapter for the runtime is **not wired yet**. An API
restart therefore clears demo and account workspace data. This is the main remaining step
toward durable production use.

## Consequences

The public demo now exercises real rules and both modes without credentials. Real accounts
work wherever Supabase Auth is configured. The legacy `FixtureJourneyStore` remains importable
for its contract tests but no longer serves traffic. Rollback is to revert the three
implementation commits; no applied migration was edited.
