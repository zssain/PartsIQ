# Single-package (build-kit) integration — handover

This tracks the `feat/single-package-integration` branch: executing the
`partsiq-build-kit/` single-workflow edition into one `apps/api/partsiq` FastAPI package
and **merging** it with the existing repo (reuse the tested `services/*` + `libs/partsiq_common`
domain logic; carry forward `apps/web`). The pre-existing multi-service build under
`services/*` is left intact on its own branches — this branch adds the consolidated package
alongside it. New tests live under `apps/api/tests/` so both builds' suites coexist.

Authoritative spec: `partsiq-build-kit/` (prompts, docs, spec). Execution order:
`partsiq-build-kit/spec/build-order.json` (00–21, 23–25, F01–F69, then 22, 26, 27).

Two real architecture changes vs the existing build:
1. LangGraph orchestrator → plain-Python fixed-transition workflow (`partsiq.workflow`).
2. Explicit Snowflake immutable source + PostgreSQL serving-cache activation
   (`partsiq.catalogue`), fixture mode as the labelled offline path.

## Done

### 00 — Bootstrap / scaffold
- Created the `apps/api/partsiq` package tree (core, api, auth, enquiries, search,
  workflow, ai, jobs, catalogue, analytics, storage, exports/templates, features,
  evaluation) with `__init__.py` markers.
- `apps/api/pyproject.toml` (`partsiq-app`, hatchling, packages=["partsiq"], deps reuse
  `partsiq-common`). Registered `apps/api` as a uv workspace member in root `pyproject.toml`.

### 01 — Typed contracts and application configuration
- `core/contracts.py`, `core/api_models.py`: copied **verbatim** from `spec/` (type names
  preserved; ruff per-file-ignore marks them vendored).
- `core/errors.py`: `PartsIQError` + `ERROR_CATALOG` (code→status/title/retryable) +
  `build_problem()` producing the RFC9457-style `Problem` contract. Internal detail never
  serialized.
- `core/settings.py`: pydantic-settings `Settings` from `spec/environment.json`;
  `load_settings()`; `runtime_dsn(role)` refuses the migration-owner URL; local/test reject a
  non-local DB URL; live AI rejected when allowance is zero or expired.
- `core/db.py`: `Database` (role-scoped asyncpg pools) + `request_scope(actor)` binding
  transaction-local `app.actor_id` via `set_config(..., true)`.
- `core/dependencies.py`: `AppContainer` + FastAPI providers (`get_settings`, `get_database`,
  `require_actor` — refuses until auth is wired in 07).
- `main.py`: `create_app()` with lifespan (pools only when a DSN is set), request-id
  middleware, Problem exception handlers (`application/problem+json`), CORS from settings,
  `/health`+`/livez` (credit-free), `/v1` router. `api/router.py`: additive `/v1` router.

Verification (exit 0): `uv run --all-packages python -m pytest apps/api/tests/test_01_core.py -q`
→ 13 passed. `uv run ruff check apps/api` → clean.

## Next
- 02 Snowflake connector + validated catalogue source; 03 Supabase schema/RLS/serving cache;
  04 storage; 05 fixtures; 06 search (port `services/search/app/*`). Then 07–17 domain, 18–20
  web, 21/23–25 ops, F01–F69, 22/26/27 gates.
