# Changes from the previous kit

| Previous statement | Revised decision | Files affected |
|---|---|---|
| LangGraph and specialist workflow | Fixed Python transition table and durable step results | Workflow, foundations09–16, contracts, dependencies |
| Separate gateway/search/orchestrator deployments | One FastAPI package and one worker image | Architecture, paths, containers, CI, deployment |
| PostgreSQL-only source catalogue | Snowflake immutable source plus validated PostgreSQL serving mirror | Catalogue, SQL, source adapters, imports, publication |
| Checkpointer library schema | workflow_runs and workflow_step_results | SQL 006; old006/007removed |
| Some F prompts only verified foundations | Every F prompt now implements its feature surface and tests | All 69 feature prompts and traces |
| Analytics from only operational records | Redacted outbox to Snowflake; scoped live counts stay PostgreSQL | Analytics, metrics, privacy, roles |
| Cloud setup described as free | Confirm allowance/expiry; explicit local fixture profile | Cost, deployment, preflight |
| Agent in AGENTS.md could imply runtime agents | Coding-assistant instructions only | AGENTS.md, CLAUDE.md, context |
| Smaller MVP suggested in conversation | Rejected; full69 scope retained | PRD, feature matrix, build order |

The original backend and original brand archive remain historical references. Their internal paths do not override this edition's application tree. Never execute historical deployment manifests directly without adapting them through the current prompts.
