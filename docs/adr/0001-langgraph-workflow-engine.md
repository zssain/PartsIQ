# ADR 0001 — LangGraph is the authoritative workflow engine (single package)

Status: Accepted (2026-10) · Supersedes the build-kit "no LangGraph" prohibition for this repo.

## Decision

The single `apps/api/partsiq` application coordinates the enquiry journey with **LangGraph**
(`partsiq.workflow.graph.build_graph`) compiled against a checkpointer. Routing is the
deterministic `partsiq.workflow.transitions.next_step` — a pure function of the typed
`EnquiryState`. **There is no LLM supervisor**: an LLM never decides which specialist runs next,
and the router/`state` modules import no langgraph and no provider client (enforced by
`test_09_workflow.py`). Compatibility filtering, stock planning, verification and approval stay in
deterministic code. The nodes reuse the existing domain functions (intake extraction, nameplate
vision, identification, compatibility search, fulfilment, reply, the verification gate).

The earlier build-kit prompt 09 forbade LangGraph; the owner has since chosen LangGraph with
deterministic routing and durable pause/resume. This ADR records that reversal; the prompts and
AGENTS/architecture docs are updated to match.

## State ownership (which system owns what)

| Concern | Owner | Key |
|---|---|---|
| Resumable graph state (the paused `EnquiryState` between steps) | **LangGraph checkpointer** — Postgres (`langgraph.checkpoint.postgres`) in prod, `InMemorySaver` in fixture/tests | `thread_id = enquiry:{enquiry_id}:rev:{revision}` |
| Enquiries, revisions, messages, candidates, drafts, decisions, jobs, audit, active-catalogue pointer | **Supabase PostgreSQL** | `enquiry_id`, `revision` |
| Step-outcome timeline (inputs/outputs/failures/retries per node, for the staff timeline + the no-replay dedup) | **PostgreSQL** via `partsiq.workflow.repository` (`workflow_step_results`) | `(enquiry_id, revision, step)` |
| Immutable catalogue source + reporting | **Snowflake**; the validated PostgreSQL serving mirror is authoritative for the *active* version | `catalogue_version_id` |

The business records in PostgreSQL are authoritative. The checkpoint is a **cache of resumable
position**, never the source of truth for a business fact (an approval, a published reply, a
catalogue version). If the two ever disagree, the DB wins and the graph re-derives its state from
the DB-backed `EnquiryState` on the next resume.

## How IDs, revisions, jobs and checkpoints relate

- An **enquiry** has a monotonically increasing **revision**. A correction/rejection starts a new
  revision (immutable snapshot of the prior one; a historical approval is never mutated — F40).
- `thread_id` binds the checkpoint to **enquiry + revision**. A new revision is therefore a *new
  thread*: an in-flight step for an old revision resumes a different thread and **cannot mutate the
  current revision's state** (stale-run isolation — F50). Verified by
  `test_workflow_langgraph.py::test_different_revision_is_a_different_thread`.
- A **job** (`JobLease`) carries `enquiry_id`, `revision`, `session_generation` and a `lease_token`.
  A worker commits a job result only if all three still match at commit time
  (`jobs.repository.finish_job`) — a stale revision or an old demo generation cannot commit.
- A **demo** carries a `session_generation`; a reset bumps it, fencing old-generation data.

## Durability & no-duplicate-action guarantees (all preserved)

- **Idempotent intake / mutations**: canonical-hash idempotency (`core.idempotency`); replay returns
  the stored result, a changed payload under the same key → `IDEMPOTENCY_MISMATCH` (409).
- **One recommendation per revision / no replayed approval**: enforced in the DB by the single
  publication index + the review-decision idempotency index (`enquiries.approval`/`publication`); a
  double-click publishes exactly once; a stale `expected_revision` → 409.
- **No stale approval after retry/restart**: resuming or approving re-checks **authentication,
  enquiry ownership, and the current revision** before acting (`auth.access.require_access` +
  `expected_revision`); an approval bound to a superseded `facts_sha256` or revision is rejected.
- **Worker leases + retry limits**: `jobs` claim/heartbeat/finish are fenced by token; a job past
  `max_attempts` is failed, not retried; a Redis push failure never loses a persisted job.
- **Clarification & human-review pauses**: blocking steps route to `END`; the checkpoint persists
  the paused state; resume is out-of-band (customer answer / reviewer decision / OCR job).
- **Event dedup (no replay)**: the durable event inbox (`consume_event` semantics) claims an event
  under a lease and re-checks revision + generation; a duplicate delivery is `obsolete`, a stale one
  is `obsolete`, a handler error is a bounded `retry`.

## Recovering from inconsistency

1. **Checkpoint ahead of DB** (crash after a node ran but before the business write committed): the
   node's StepOutcome was fenced-committed or not; on resume the step is replayed idempotently
   (same `(enquiry,revision,step)` + input hash → no re-run, no duplicate side effect).
2. **DB ahead of checkpoint** (checkpoint lost / Redis down): the graph rebuilds `EnquiryState` from
   the DB (items, selections, draft_id, verification_id, phase) and resumes; the lost checkpoint is
   only a position cache.
3. **Approval already published** but the graph still shows `review`: `next_step` sees the reviewed
   phase and routes to `complete`; publication is single-shot by index, so no second reply is sent.

## Migrating existing plain-Python workflow runs

The earlier consolidation used a plain-Python `run_next` loop. There is **no live DB in this
environment**, so there are no persisted graph runs to migrate here. The forward path is defined:
a plain-Python run is fully described by its last committed `StepOutcome` for `(enquiry, revision)`;
on the first LangGraph resume the checkpoint is **seeded** from the `EnquiryState` reconstructed from
those committed outcomes (idempotent — a step already recorded is not re-run). `run_next` is retained
as the fenced step/timeline/dedup primitive, so the two share one transition table and cannot
disagree about the next step.

## Rollback path

The legacy `services/orchestrator` LangGraph runtime remains in the tree and is **not retired until**
the consolidated engine passes the full journey + resilience checks (ADR Phase 6). Rollback =
continue routing workflow traffic to `services/orchestrator` (its graph/checkpointer are unchanged).
Retirement is a separate, reversible commit.
