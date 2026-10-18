# Dependencies and installation

> **SUPERSEDED (2026-10) — see `docs/adr/0001-langgraph-workflow-engine.md` (repo root).**
> The owner has adopted **LangGraph with deterministic routing** as the single authoritative
> workflow engine: fixed transitions are decided in code (`partsiq.workflow.transitions.next_step`),
> there is **no LLM supervisor**, and compatibility/verification/approval stay deterministic.
> Any statement in this document that forbids or excludes LangGraph is OBSOLETE. The
> consolidated engine lives in `apps/api/partsiq/workflow` and is proven by
> `apps/api/tests/test_workflow_langgraph.py` + `test_journey_e2e.py`.


Direct package releases were verified from official registries in the original kit and Snowflake was verified for this revision. Existing pins are deliberately preserved except removed agent/checkpoint libraries and the added Snowflake connector. This is not a vulnerability certification. Python resolution was rerun for this edition; the frozen frontend manifest/lock is retained. Run actual target-runtime builds in CI.

| Package | Exact version | Release date | Install owner | Purpose |
|---|---|---|---|---|
| fastapi | 0.135.1 | 2026-03-01 | 00 | Typed REST routing and generated OpenAPI |
| uvicorn | 0.41.0 | 2026-02-16 | 00 | ASGI process |
| pydantic | 2.12.5 | 2025-11-26 | 00 | Strict DTOs and domain contracts |
| pydantic-settings | 2.13.1 | 2026-02-19 | 00 | Validated environment configuration |
| httpx | 0.28.1 | 2024-12-06 | 00 | Bounded HTTP clients |
| asyncpg | 0.31.0 | 2025-11-24 | 00 | PostgreSQL transactions and serving queries |
| psycopg | 3.3.3 | 2026-02-18 | 00 | Schema/operator utilities |
| redis | 7.3.0 | 2026-03-06 | 00 | Rate limits and wakeups |
| openai | 3.19.2 | 2026-09-24 | 00 | Structured text and image calls |
| structlog | 25.5.0 | 2025-10-27 | 00 | Redacted JSON logs |
| tenacity | 9.1.2 | 2025-04-02 | 00 | Bounded retry support |
| PyJWT | 2.12.1 | 2026-03-13 | 00 | JWT verification |
| cryptography | 46.0.5 | 2026-02-10 | 00 | Key material and cryptographic primitives |
| sentence-transformers | 5.2.3 | 2026-02-17 | 00 | BGE-M3 wrapper |
| transformers | 4.57.6 | 2026-01-16 | 00 | Model loading |
| torch | 2.10.0 | 2026-01-21 | 00 | CPU inference only |
| numpy | 2.4.2 | 2026-01-31 | 00 | Vector checks and ranking |
| Jinja2 | 3.1.6 | 2025-03-05 | 00 | Escaped export HTML |
| Pillow | 12.1.1 | 2026-02-11 | 00 | Image verification and sanitation |
| playwright | 1.58.0 | 2026-01-30 | 00 | Chromium PDF rendering |
| openpyxl | 3.1.5 | 2024-06-28 | 00 | Nonexecuting XLSX parsing |
| PyYAML | 6.0.3 | 2025-09-25 | 00 | Configuration tools |
| pytest | 9.0.2 | 2025-12-06 | 00 | Backend tests |
| pytest-asyncio | 1.3.0 | 2025-11-10 | 00 | Async backend tests |
| ruff | 0.15.6 | 2026-03-12 | 00 | Python lint |
| mypy | 1.19.1 | 2025-12-15 | 00 | Python type checks |
| uv | 0.10.9 | 2026-03-06 | 00 | Frontend application, styling, types or test tooling as declared in web-package.json |
| langfuse | 3.14.5 | 2026-02-23 | 00 | Optional redacted traces |
| python-docx | 1.2.0 | 2025-06-16 | 00 | Frontend application, styling, types or test tooling as declared in web-package.json |
| pypdf | 6.8.0 | 2026-03-09 | 00 | PDF test extraction |
| python-multipart | 0.0.22 | 2026-01-25 | 00 | Upload-related form parsing |
| next | 16.2.12 | 2026-07-25 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| react | 19.2.6 | 2026-05-06 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| react-dom | 19.2.6 | 2026-05-06 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| typescript | 5.9.3 | 2025-09-30 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| tailwindcss | 4.1.18 | 2025-12-11 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| @tailwindcss/postcss | 4.1.18 | 2025-12-11 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| postcss | 8.5.6 | 2025-06-16 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| @supabase/supabase-js | 2.99.1 | 2026-03-11 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| @supabase/ssr | 0.8.0 | 2025-11-26 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| next-intl | 4.8.3 | 2026-02-16 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| zod | 4.6.5 | 2026-09-13 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| vitest | 4.1.11 | 2026-08-18 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| @playwright/test | 1.58.2 | 2026-02-06 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| eslint | 9.39.1 | 2025-11-03 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| eslint-config-next | 16.2.12 | 2026-07-25 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| @testing-library/react | 16.3.0 | 2025-04-02 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| @testing-library/dom | 10.4.1 | 2025-07-27 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| @testing-library/jest-dom | 6.9.1 | 2025-10-01 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| @testing-library/user-event | 14.6.1 | 2025-01-21 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| jsdom | 27.4.0 | 2025-12-26 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| @vitejs/plugin-react | 5.1.4 | 2026-02-10 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| @types/react | 19.2.14 | 2026-02-11 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| @types/react-dom | 19.2.3 | 2025-11-12 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| @types/node | 22.19.15 | 2026-03-06 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| clsx | 2.1.1 | 2024-04-23 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| tailwind-merge | 3.5.0 | 2026-02-18 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| class-variance-authority | 0.7.1 | 2024-11-26 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| lucide-react | 0.577.0 | 2026-03-04 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| radix-ui | 1.4.3 | 2025-08-13 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| shadcn | 4.20.1 | 2026-09-02 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| pnpm | 10.30.3 | 2026-02-26 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| supabase | 2.75.0 | 2026-02-02 | 18 | Frontend application, styling, types or test tooling as declared in web-package.json |
| snowflake-connector-python | 4.8.0 | 2026-09-30 | 02 | Parameterized Snowflake catalogue/reporting access |

## Commands

Foundation 00: uv venv --python 3.12, then uv pip sync spec/python-requirements.lock. Copy the selected runtime dependencies into pyproject.toml and generate the project lock without changing pins. The supplied reference lock includes test/tool dependencies for reproducibility; production image may use a derived runtime subset with the same versions. Pin the exact CPU torch wheel URL/hash from the lock; do not install CUDA packages on the CPU host.

Foundation 18: copy spec/web-package.json to apps/web/package.json and spec/pnpm-lock.yaml to apps/web/pnpm-lock.yaml; run corepack pnpm --dir apps/web install --frozen-lockfile. Node 22.22.0 is the target. The earlier frontend resolver ran on Node 24; the target build still needs execution. Use packageManager pnpm10.30.3. PythonPlaywright1.58.0 and webPlaywright1.58.2 are separate installations; install each browser binary with its own CLI and never share an unversioned browser cache between them.

Foundation 02 uses snowflake-connector-python4.8.0 already included in the reference lock. No Snowpark, Pandas, agent framework or Cortex SDK is needed. Langfuse is optional and never on the business-critical path. Do not restore LangGraph through a transitive convenience dependency.

## Upgrade policy

Before a dependency change, record the reason, official release date, target-runtime compatibility and security impact. Resolve the complete lock, run focused regression tests and document the new receipts. A package existing on a registry is not proof that the application is compatible or secure. Do not claim all transitives meet the14-day release criterion unless each has been independently verified; the explicit criterion applies to the direct pins in the receipt table.
