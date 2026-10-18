# Coding agent instructions

> **SUPERSEDED (2026-10) — see `docs/adr/0001-langgraph-workflow-engine.md` (repo root).**
> The owner has adopted **LangGraph with deterministic routing** as the single authoritative
> workflow engine: fixed transitions are decided in code (`partsiq.workflow.transitions.next_step`),
> there is **no LLM supervisor**, and compatibility/verification/approval stay deterministic.
> Any statement in this document that forbids or excludes LangGraph is OBSOLETE. The
> consolidated engine lives in `apps/api/partsiq/workflow` and is proven by
> `apps/api/tests/test_workflow_langgraph.py` + `test_journey_e2e.py`.


## Mission and authority

Build PartsIQ from this single-workflow Snowflake edition. The term agent in this file means the coding assistant executing prompts; it does not authorize an AI-agent architecture in the product. Preserve all 69 features. No supervisor, specialist team, LangGraph, LangChain, CrewAI or LLM tool-calling loop is required or allowed by this design.

Authority order: current user instructions, these rules, docs/CONSTRAINTS.md, approved architecture/ADRs, typed contracts/SQL/API specification, current prompt. If two approved specifications conflict, report the concrete conflict and propose a minimal repair before implementing incompatible behavior. Do not silently reinterpret an unknown business rule.

## Work method

Execute one prompt at a time in spec/build-order.json. Read its prerequisites and current docs/HANDOVER.md. State the planned files, interfaces and tests; routine reversible implementation is authorized. Inspect existing code before writing. Preserve the supplied legacy archive and port its tested search logic into the single package instead of recreating it from memory.

Use rg to locate symbols. Prefer small cohesive functions with typed inputs and explicit side effects. Routers handle transport; feature facades handle user cases; domain modules own decisions; repositories handle persistence. Do not put SQL or credentials in React components. Do not copy compatibility, approval or budget rules into feature modules.

For every task: implement the specified behavior, run focused tests, inspect the diff, record real evidence, commit, update handover and feature traces. A file named test does not prove a behavior passed. Never fabricate test counts, accuracy, latency, production use, customer adoption or recorded videos. A blocked provider check is not passed.

## Critical invariants

1. Resolve a confirmed machine configuration before ranking its compatible part set.
2. Only activate a Snowflake catalogue version after explicit validation and atomic PostgreSQL serving-cache publication.
3. Missing information and close candidates produce questions or staff review, not guesses.
4. No recommendation is published without a current revision-bound human decision and audit record.
5. Customer identity and staff roles derive from verified authentication and server-side records.
6. Every durable job completion is fenced by lease token, revision and demo generation.
7. AI budget reservation happens before every external attempt; uncertain usage stays reserved until reconciled.
8. No paid fallback, no voice, no quotation builder, no orders/reservations, no external messages.

## Tools and dependencies

Use the package pins and locks supplied in spec. Do not install a new library merely because its API is convenient. If a pinned dependency fails on the target runtime, record the failure and propose the smallest justified change with a new lock and tests. Never loosen all pins to make a resolver pass.

Use a disposable local database for tests. Never run schema resets, seed scripts or destructive queries against production. Keep secrets in ignored environment files or provider secret stores. Do not echo keys, JWTs, signed URLs or database passwords into logs. No runtime uses the schema-owner credential.

## Completion format

Report changed behavior, paths, commands and actual results, remaining blockers, and commit. Append docs/SESSION_LOG.md. Update docs/HANDOVER.md with the next prompt. Feature traces remain specified until tests and implementation exist. Stop to clarify only when blocked by an actual missing business decision, required credential/account access or destructive operation; continue all other authorized work.
