# Current handover

State: prompt 00 executed in-place; this folder is now the application repository (git initialised, baseline tagged `pre-00`, work on branch `prompt/00-bootstrap`). The legacy search/gateway/catalogue code is preserved at its original relative paths and still bundled in references/legacy-backend.zip.

Completed through 00:
- Legacy backend extracted to repo root, verified byte-for-byte against the zip (65 files, 0 mismatches). Preservation manifest at references/legacy-backend.sha256.
- Single uv workspace created (root pyproject.toml); uv-managed members: libs/partsiq_common, services/orchestrator (skeleton), services/worker (skeleton). One uv.lock (36 packages; pinned CPython 3.12.12).
- Tooling: tools/verify_env.py (`verify_environment`), tools/run_checks.py (per-process test dispatch + no-prod-DB gate), tools/check_release_eligibility.py, tools/catalog/__init__.py.
- Config: .python-version (3.12.12), .nvmrc (22.22.0), .gitignore (superset), .env.example (superset of spec/environment.json + preserved legacy compose vars).
- tests/foundations/test_00.py (stdlib unittest, 15 cases).

Commands actually run (all exit 0):
- `python tools/run_checks.py --prompt 00` → `foundations/test_00.py PASS` (15 tests).
- `uv run --python 3.12.12 python tools/run_checks.py --prompt 00` → exit 0 under the pinned interpreter.
- `uv lock` → Resolved 36 packages; `uv run ruff check` on new files → All checks passed.
- `python tools/check_release_eligibility.py` → 66 receipts, all at/before cutoff 2026-09-26.
- `python tools/kit/verify_kit.py` → KIT VALIDATION PASSED (unchanged).

Implementation notes / deviations (within approved scope, one-creator rule in AGENTS.md §3):
- gateway/search/catalogue have no pyproject.toml in spec/file-ownership.json, so they remain legacy requirements.txt services run in ISOLATED test processes (they share the `app` import name); they are intentionally not uv workspace members.
- docker-compose.yml kept as the preserved legacy local stack (already binds gateway to 127.0.0.1). Full local Supabase-CLI wiring (supabase/config.toml) is prompt 02's scope — not pre-built here.
- orchestrator/worker pyproject.toml are dependency-free skeletons; their runtime deps and app code arrive in their owning prompts (09/04/15). No forward dependency introduced.
- root README.md is now the preserved legacy application README (prompt 00 owns README.md); the build-kit README remains in git history under tag `pre-00`.

Completed through 01 (Common):
- partsiq_common upgraded to TECH_SPEC pins (fastapi 0.135.1, pydantic 2.12.5, psycopg 3.3.3, openai 3.19.2, …) with asyncpg retained for legacy. uv re-locked (56 packages) and synced; all common modules (legacy + new) import cleanly.
- contracts.py copied verbatim from spec/contracts.py; errors.py (public envelope + code→HTTP map); ai/client.py (`call_structured`, SDK max_retries=0 + 2 wrapper attempts, output-token cap, structured-output validation, trusted/untrusted message split); ai/budget.py (allowance gate: paid budget must be 0, unknown price blocks, expiry blocks, atomic caps) + ai/prices.json; telemetry.py (monotonic staging, redaction, outage-safe tracer); security_context.py (`actor_transaction` with transaction-local `app.actor_id`); audit.py (`append_audit` in caller tx, redacted, append-only).
- Root pyproject now depends on partsiq-common so `uv sync` installs its runtime deps.
- tests/foundations/test_01.py: 27 stdlib cases (fakes for OpenAI + DB), all pass; `run_checks --prompt 01` exits 0; prompt 00 regression still green; ruff clean.

Completed through 02 (Database — catalogue):
- spec/sql/001 and 002 copied byte-for-byte into supabase/migrations/20261011000100_legacy_catalogue.sql and ..000200_legacy_search.sql (verified identical). supabase/config.toml (local only; managed versions deferred to the prompt-03 schema receipt). tools/apply_catalogue_schema.py applies additively via `supabase migration up` and refuses any reset/destructive command.
- test_02.py: 10 cases pass (1 live-DB case skipped) — verifies verbatim copies, the serial-range EXCLUDE/compatibility/supersession-RECURSIVE/transfer_days constraints, and the no-reset guard. Applying to a real DB is BLOCKED (no Supabase/Postgres here).

Completed through 03 (Database — workflow schema & permissions):
- spec/sql/003 and 004 copied verbatim into supabase/migrations/..000300_application.sql and ..000400_rls.sql (48 RLS tables, 113 policies, 5 NOLOGIN group roles, app_private actor/role/demo helpers). tools/checkpoints_setup.py applies the extracted checkpoint DDL (spec/sql/006) in autocommit then the permissions (007) in a transaction, refusing resets; it adds no new package (uses the extracted DDL, not a langgraph import). tools/schema_receipt.py (`collect_schema_receipt`) reads the live catalog read-only. tests/integration/conftest.py scaffolds a disposable-DB pool that skips without a reachable DATABASE_URL and enforces the prod denylist.
- test_03.py: 12 cases pass (1 live-DB skip) — verbatim copies, role model, per-item/revision candidate keys, no-invented-identity backfill, single-publication backstop, transaction-local app.actor_id, checkpoint autocommit→tx order, schema-receipt shape. Live RLS/two-actor enforcement BLOCKED (no Postgres here).

Completed through 04 (Gateway/worker — private storage):
- spec/sql/005 copied verbatim into supabase/migrations/..000500_storage.sql (4 private buckets; nameplate owner+pending RLS policy). services/gateway/app/storage.py (`create_upload` with the user token to a unique pending key; `sign_download` authorize-then-delegate to the worker with a typed resource id; magic-byte validation; 60s links; log redaction). services/worker/app/storage.py (sole Storage-admin holder; `sign_download` resolves a typed resource to bucket+key; `remove_object`; no DB-REST surface) + services/worker/app/__init__.py.
- test_04.py: 14 cases pass (2 deferred skips) — magic validation, unique key, 60s expiry, redaction, contract size/MIME bounds, typed delegation, nonexistent object, bucket validation. Decoded-pixel cap/EXIF (prompt 16) and duplicate-confirmation (prompt 08) are explicitly deferred; live Supabase Storage is BLOCKED here.

Completed through 05 (Catalogue — synthetic fixtures):
- tools/demo/build_scenarios.py (`build_scenarios`, `validate_scenarios`, `render_nameplate`) derives the four demo scenarios from REAL seed-42 records (database ids == 1-based load ordinals), and refuses to emit an undemonstrable scenario. tools/demo/render_assets.py generated scenarios.json, the four scenarios/*.json, a nameplate PNG, a cited evidence PDF, and hash manifests. Pillow 12.1.1 added to the workspace and re-locked.
- test_05.py: 9 cases pass — determinism, scenario shapes, valid-set acceptance, rejection of an incompatible expected part and of an unsupported stock claim (F02), real PNG rendering, committed-fixture match.
- verify_kit.py scoping fix: the markdown "unfinished prose" scan now skips uncommitted build dirs (.venv, node_modules, .git); authored-doc enforcement is unchanged. KIT VALIDATION PASSES.

Full regression: run_checks --prompt 00..05 all exit 0.

Completed through 06 (Search — extend legacy):
- Characterized the preserved legacy domain (identify_machine, LexicalScorer, plan_fulfilment, parse_serial) in services/search/tests/test_characterization.py. Added internal-token auth to all search routes (constant-time; unconfigured = local dev) + a /readiness route reporting lexical readiness and semantic capability SEPARATELY. Added services/search/app/embedding_ingestion.py (`embed_version`: 1024-d/unit-norm/NaN validation, source-sha256, model_revision; provider+store injected). Fixed service.py: runner-up margin computed over the full ranked set BEFORE the response limit (F25), NaN scores rejected, and a superseded part's current successor is offered only with its OWN explicit fitment (ADR-018/F30). Extended partsiq_common.embeddings (validate_embedding, source_sha256), repository (embedding store methods), tools/catalog embedder (source_sha256+model_revision), search config/Dockerfile/requirements-embeddings (CPU-wheel pins recorded, not installed).
- Tests: run_checks --prompt 06 → test_06.py PASS (10); full search suite PASS (71 incl. preserved legacy + F20/F21/F22/F23/F24/F25/F30/F33/F34) via isolated pytest. All offline with an in-memory fake repository + fake encoder.
- BLOCKED (reported, not faked): live asyncpg/pgvector retrieval, real BGE-M3 load + weights, torch/sentence-transformers install (CPU wheels recorded in requirements-embeddings.txt but not installed — ~2.5 GB on a near-full disk), and embedding of a real published catalogue version.

Next: execute prompt 07 (Authentication and demo sessions) per prompts/README.md, on its own branch.

Watch: AWS Free Plan eligibility and actual BGE/Chromium sizing; owner-confirmed OpenAI credit; assigned-only permissions; no fake production-readiness claims. Live OpenAI and live-DB behaviour for AI/audit/actor-context remain integration work (tested here only with in-process fakes).

Evidence: docs/SESSION_LOG.md records this session and the coding model. Runtime, Supabase, and hosted acceptance remain implementation work.
