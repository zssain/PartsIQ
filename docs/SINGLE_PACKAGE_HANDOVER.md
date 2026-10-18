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

## Progress log (branch `feat/single-package-integration`)

All commits below are green (`uv run --all-packages python -m pytest apps/api/tests` + `uv run ruff check apps/api`). New tests live under `apps/api/tests/` so the earlier multi-service suite is untouched.

- **00–01** scaffold + core (contracts/api_models verbatim, errors/settings/db/dependencies/main/router).
- **02 catalogue + 04 storage** — Snowflake source (injected connector, bound SQL, order-independent hash) + infra/snowflake DDL; private storage (magic+pixel validation, typed-resource signing, 60s links).
- **03 schema + 05 fixtures** — verbatim 001–005 migrations + `catalogue/activation.py` (validate→copy→atomic pointer flip, compare-and-set, same-tx audit); deterministic seed-42 `catalogue/fixtures.py` + `fixtures/catalogue.json`,`scenarios.json`.
- **06 search + 07 auth** — ported `services/search` domain into `partsiq.search` (compatible-only, margin over full ranked set, F20-F34); ported gateway auth (JWKS refresh-once RS256, DB-sourced roles, assigned-only review, demo generation isolation).
- **08 intake + 10 extraction** — idempotency/rate-limit, enquiry+job one-tx 202, history keyset; `ai/client` (max_retries=0, token cap, trusted/untrusted split), `ai/budget` (paid=0/expiry block, atomic reserve), `ai/extraction`.
- **09 workflow + 12 verification** — FIXED transition table, durable fenced runner **(NO LangGraph)**; seven pure checks, aggregate overallocation, order-independent Decimal-stable `facts_sha256`.
- **11 resolution + 13 drafts** — local-first fulfilment, bilingual clarify/ambiguity-no-guess; fact-free reply slots (reject digits/identifiers), code-owned renderer (html-escape, RTL `<bdi>`, no price).
- **14 approval + 15 jobs** — locked review tx (assigned-only 404, revision 409, idempotent publish-once, same-tx audit, F40/F47/F49); lease/heartbeat/finish fenced by token+revision+generation, sweeper, worker main (F51/F52/F05).
- **16 vision + 17 exports** — code forces attachment_id + confirmation_required, verbatim serial; approved-immutable-only PDF via injected HTML→PDF port, lease-fenced record.
- **21 evaluation + 23 analytics** — deterministic no-OpenAI eval (abstentions separate, dataset hash) + curation; outage-safe redacting tracer, idempotent EVENT_ID outbox, staff-only metrics, `validate_allowance`.
- **24 containers + 25 CI** — one-image Dockerfile (api+worker), Caddy edge, prod/fixture compose, image verifier; SHA-pinned CI + workflow_dispatch deploy with OIDC + migrate-before-deploy + INFRA_READY gate (named `*-partsiq` to coexist).
- **API wiring** — `build_container` fixture adapters (seed-42 catalogue, in-memory demo + journey), fixture actor verifier (`X-Demo-Token`), `api/router` additive aggregator, `main` lifespan. End-to-end TestClient integration test (fixture mode).
- **Feature routers F01–F65, F67** wired into `/v1` (77 routes, no collisions): customer/demo (F01-F19), search/candidate/catalogue (F20-F35,F57), staff review (F36,F37,F39,F41,F42,F43,F47,F49), OCR (F14-F17), and review/ops/analytics extras (F38,F40,F44-F46,F50-F65,F67). DB/provider-backed routes return a clean 503 offline (never fabricated). Facade-only (cross-cutting, no endpoint): F48 input isolation, F53 graceful failures.
- **Web** — `apps/web/lib/api.ts` retargeted at the single-package `/v1` (NEXT_PUBLIC_API_ORIGIN), parses RFC9457 Problem, sends `X-Demo-Token`; existing revamped UI unchanged. tsc clean, 44 web tests pass.
- **22 security gate** (offline portion) — disposable-env guard, F48 AI input isolation, app access (401/404-no-leak/demo isolation), F53 safe Problem bodies.

Current: **622 Python tests pass, 15 skipped** (all skips = live-infra BLOCKED, never faked), ruff clean; app boots and serves **77 `/v1` routes**; the fixture customer+demo journey returns real seed-42 data end-to-end.

## Remaining / BLOCKED
- **Gates 26 (AWS) + 27 (Vercel/hosted acceptance)**: deployment-receipt gates — entirely BLOCKED here (no AWS/Vercel/Supabase account). The services build already carries `infra/ec2/preflight.py` + `tools/hosted_acceptance.py`; re-port only when an account exists. Not re-created to avoid near-empty duplicates.
- **Live infrastructure** (unchanged, reported not faked): Supabase Postgres/Auth/RLS/Storage, Redis, Snowflake (connector not installed), live OpenAI text+vision, pgvector + BGE-M3 (torch not installed), Playwright/Chromium PDF. Every domain path behind these is tested with in-memory fakes + injected ports; the fixture profile is the labelled no-provider path.
- **Web feature panels** (`apps/web/src/features/fNN/Panel.tsx`, 69 files) from prompts 18-20/F01-F69 were intentionally NOT regenerated — the existing revamped `apps/web` is kept as the UI and wired to `/v1` via the typed client (the "merge" decision). Re-scaffolding the kit's parallel `src/` panels would conflict with the revamp.
- A few feature **facades** exist without a mounted router where the kit defines no distinct `/v1` endpoint (cross-cutting/doc/web features: F48, F53, F66 tests-CI, F68 recruiter docs, F69 demo walkthrough).

## Migrations coexistence (reconciliation item)
`supabase/migrations/` now holds BOTH the earlier timestamped multi-service migrations and the build-kit `001_`–`005_` files (kit `001/002/003` are byte-identical to the legacy ones; `004_rls`/`005_storage` differ slightly). Live apply is BLOCKED; pick one naming scheme before applying to a real DB.
