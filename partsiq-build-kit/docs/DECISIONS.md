# Architecture decisions

> **SUPERSEDED (2026-10) — see `docs/adr/0001-langgraph-workflow-engine.md` (repo root).**
> The owner has adopted **LangGraph with deterministic routing** as the single authoritative
> workflow engine: fixed transitions are decided in code (`partsiq.workflow.transitions.next_step`),
> there is **no LLM supervisor**, and compatibility/verification/approval stay deterministic.
> Any statement in this document that forbids or excludes LangGraph is OBSOLETE. The
> consolidated engine lives in `apps/api/partsiq/workflow` and is proven by
> `apps/api/tests/test_workflow_langgraph.py` + `test_journey_e2e.py`.


## ADR001 Extend the legacy backend

Accepted. Preserve the supplied backend archive and characterize its identification, lexical ranking and fulfilment behavior. Consolidate those modules under partsiq.search in the new package through explicit import/path adaptation. Do not rewrite working algorithms just to change framework shape. Original source remains available for comparison.

## ADR002 Hosting and cost

Amended. Next.js remains on Vercel and Supabase remains managed. One EC2 instance runs Caddy, API, worker and Redis using Docker Compose only when confirmed AWS allowance covers the deployment. Render is a documented alternative, not the chosen deployment. No long-term free-hosting claim. A local fixture deployment remains supported.

## ADR003 Replace multi-agent orchestration

Accepted16 October 2026. User requested the complete pre-multi-agent feature set with a simpler runtime. Remove LangGraph, checkpoint-library tables, supervisor routing, specialist agents and internal search/orchestrator HTTP services. Use ordinary Python functions, fixed transitions, PostgreSQL step results and durable leased jobs. This changes implementation architecture, not feature scope.

## ADR004 Snowflake source with validated relational serving

Accepted for this revision. Snowflake holds versioned source catalogue/inventory and reporting data. Supabase PostgreSQL stores application records and a validated serving mirror. Standard Snowflake PK/FK declarations do not enforce uniqueness/referential integrity; publication validation and PostgreSQL constraints are retained. Activation is atomic locally; cross-system upload is recoverable and not falsely described as a distributed transaction.

## ADR005 Single active source mode

Accepted. DATA_SOURCE is fixture or snowflake and must be explicit. A live provider error never silently changes source. Both modes use identical validators. UI and receipts display provenance and freshness. Fixture results cannot count as live provider evidence.

## ADR006 Scope and roles

Accepted. All 69 groups retained with one detailed feature implementation prompt each. No voice or quotation builder. Public demo uses anonymous Supabase users and session isolation; real users are invited and real onboarding stays disabled until retention is configured. Reviewers access assigned enquiries; admins manage assignment.

## ADR007 No paid fallback

Accepted. User supplied free keys and a zero-paid-spend budget. The application reserves only confirmed available allowance with expiry and does not infer credit balance from key validity. Snowflake trial and cloud account eligibility are operator preflight items. No new paid provider is selected automatically.
