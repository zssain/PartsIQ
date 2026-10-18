# PartsIQ single workflow Snowflake build kit

> **SUPERSEDED (2026-10) — see `docs/adr/0001-langgraph-workflow-engine.md` (repo root).**
> The owner has adopted **LangGraph with deterministic routing** as the single authoritative
> workflow engine: fixed transitions are decided in code (`partsiq.workflow.transitions.next_step`),
> there is **no LLM supervisor**, and compatibility/verification/approval stay deterministic.
> Any statement in this document that forbids or excludes LangGraph is OBSOLETE. The
> consolidated engine lives in `apps/api/partsiq/workflow` and is proven by
> `apps/api/tests/test_workflow_langgraph.py` + `test_journey_e2e.py`.


This kit specifies the complete69-feature PartsIQ application with a conventional Python workflow. It replaces the earlier multi-agent design while retaining the customer, staff, catalogue, analytics, security and recruiter-demo features. Voice and quotation building remain excluded.

This is an implementation kit, not a completed or deployed application. Follow 97 detailed prompts in prompts/README.md: foundations00–21 and23–25,featuresF01–F69,then final gates22 and26–27. Source contracts, SQL and dependency locks are supplied as exact implementation inputs. Test receipts must be produced by the coding agent as it builds the application.

## Start here

1. Read AGENTS.md and docs/CONTEXT.md.
2. Read docs/PRD.md, docs/ARCHITECTURE.md and docs/DATA_OWNERSHIP.md.
3. Create your project repository and place this kit at its root. Keep references/legacy-backend.zip unchanged.
4. Open prompts/README.md and execute prompt 00 first. Do not paste all 97 prompts into one coding-agent turn.
5. Give the agent the complete current prompt and permission to inspect the repository. After each step, require real tests, a commit, and an updated handover.
6. Enable live Snowflake/OpenAI only after confirmed account allowance checks. Explicit fixture mode runs synthetic demos without either provider.

## What is included

- 97 implementation prompts and69 feature traces.
- PRD, architecture, workflow, REST API, security, Snowflake, data ownership, deployment, rollback and handover documents.
- Typed Python models and a machine-readable OpenAPI3.1 specification.
- Supabase and Snowflake DDL, dependency manifests and resolved reference locks.
- The original backend, logo/brand pack and collaboration field guide.
- A regenerated complete guide and checksums for the archive contents.

## Locked product choices

Next.js on Vercel; Supabase Auth, PostgreSQL and Storage; one FastAPI application plus a worker from the same image; Redis for rate limits and wakeups; Snowflake for versioned catalogue source and reporting; OpenAI for extraction, vision and constrained prose; optional BGE-M3 inside the worker search module. No LangGraph or autonomous agent routing.

Snowflake's trial is time/credit limited, not a permanent free plan. AWS eligibility and Vercel plan terms are account specific. The local fixture profile is the no-provider-cost fallback and must always be labelled accurately. The kit does not activate accounts, spend credits or claim production readiness by itself.
