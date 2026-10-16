# Session log

## 2026-10-11 - Build-kit generation
1. Work: incorporated owner decisions and generated the complete implementation kit.
2. Decisions: retain OpenAI; paid budget0;assigned-only review;69 grouped features;public synthetic demo.
3. Verification: see SELF_AUDIT.md for actual artifact checks and their limits.
4. Next: coding agent executes00;no application deployment performed during kit creation.
5. Model/version: not exposed by this authoring environment; no version invented.

## 2026-10-17 - Prompt 00 (bootstrap and preserve legacy)
1. Work: git init + baseline tag `pre-00`; branch `prompt/00-bootstrap`. Extracted legacy backend to repo root (65 files, byte-for-byte verified, manifest references/legacy-backend.sha256). Created root uv workspace + uv.lock (36 pkgs, CPython 3.12.12), orchestrator/worker skeleton pyprojects, config dotfiles, .env.example superset, and tools/verify_env.py, run_checks.py, check_release_eligibility.py, catalog/__init__.py, tests/foundations/test_00.py.
2. Verification (actual, all exit 0): `python tools/run_checks.py --prompt 00` → test_00.py PASS (15 tests); same under `uv run --python 3.12.12`; `uv lock` resolved 36 packages; ruff clean on new files; check_release_eligibility → 66 receipts within cutoff; verify_kit still PASSED.
3. Deviations (within approved scope): gateway/search/catalogue stay legacy requirements.txt services in isolated test processes (no pyproject in file-ownership); docker-compose kept as preserved legacy (Supabase-CLI local wiring deferred to prompt 02); root README is now the legacy app README (kit README retained under tag pre-00). uv.lock holds legacy common pins until prompt 01 upgrades them.
4. Next: prompt 01 (shared contracts and clients).
5. Model/version: claude-opus-4-8[1m] (Claude Opus 4.8, 1M context) — coding agent executing prompt 00.

## 2026-10-17 - Prompt 01 (shared contracts and clients)
1. Work: upgraded partsiq_common pins to TECH_SPEC (fastapi 0.135.1/pydantic 2.12.5/psycopg 3.3.3/openai 3.19.2/…; asyncpg kept for legacy). Added contracts.py (verbatim from spec), errors.py, ai/client.py (call_structured), ai/budget.py + prices.json, telemetry.py, security_context.py (actor_transaction), audit.py (append_audit). Root now depends on partsiq-common; uv re-locked+synced.
2. Verification (actual, exit 0): `run_checks --prompt 01` → test_01.py PASS, 27 stdlib cases with OpenAI/DB fakes; prompt 00 still PASS; ruff clean; all common modules import under the new pins.
3. Scope/limits: SDK max_retries=0 + 2 wrapper attempts verified; paid-budget=0, unknown-price-blocks, expiry-blocks, atomic cap verified; audit redaction + rollback-on-failure verified; actor_transaction sets transaction-local app.actor_id. Live OpenAI and live Postgres remain integration-only (fakes used here).
4. Next: prompt 02 (catalogue migration).
5. Model/version: claude-opus-4-8[1m] (Claude Opus 4.8, 1M context).

## 2026-10-17 - Prompt 02 (catalogue migration)
1. Work: copied spec/sql/001 & 002 byte-for-byte into supabase/migrations (legacy_catalogue, legacy_search); added supabase/config.toml (local) and tools/apply_catalogue_schema.py (additive `migration up`, refuses reset).
2. Verification (exit 0): `run_checks --prompt 02` → test_02.py PASS (10 tests, 1 live-DB skip); ruff clean. Verbatim copy + serial-exclusion/compatibility/supersession-RECURSIVE/transfer_days + no-reset guard asserted.
3. Limits: applying to a real database is BLOCKED (no Supabase/Postgres here); F20/F22/F28/F30 runtime behaviour owned by prompt 06.
4. Next: prompt 03 (workflow schema and database permissions).
5. Model/version: claude-opus-4-8[1m].

## 2026-10-17 - Prompt 03 (workflow schema and database permissions)
1. Work: copied spec/sql/003 & 004 verbatim into supabase/migrations (application, rls). Added tools/checkpoints_setup.py (extracted checkpoint DDL in autocommit then 007 permissions in a tx; no langgraph dep; refuses reset), tools/schema_receipt.py (collect_schema_receipt, read-only), tests/integration/conftest.py (disposable-DB pool, skips without DB, prod denylist).
2. Verification (exit 0): `run_checks --prompt 03` → test_03.py PASS (12 tests, 1 live-DB skip); new files ruff-clean (pre-existing legacy/kit ruff findings left untouched). Asserted verbatim copies, 5 NOLOGIN roles, 48 RLS tables/113 policies, per-item/revision candidate keys, no-invented-identity backfill, single-publication index, transaction-local app.actor_id, checkpoint setup order, schema-receipt shape.
3. Limits: live RLS enforcement + two-actor-on-reused-pool BLOCKED (no Postgres here); run under tests/integration against disposable Supabase.
4. Next: prompt 04 (private storage).
5. Model/version: claude-opus-4-8[1m].

## 2026-10-17 - Prompt 04 (private storage)
1. Work: copied spec/sql/005 verbatim into supabase/migrations (4 private buckets, nameplate owner+pending policy). Added services/gateway/app/storage.py (create_upload, sign_download delegate, magic validation, 60s, redaction), services/worker/app/storage.py (admin-only signer + remove_object, no DB REST), services/worker/app/__init__.py.
2. Verification (exit 0): `run_checks --prompt 04` → test_04.py PASS (14 tests, 2 deferred skips); new files ruff-clean. Division of trust (gateway user-token upload vs worker admin signing), typed resource delegation, 60s expiry, magic-byte spoof rejection, nonexistent-object 404, bucket validation asserted.
3. Limits: decoded-pixel cap/EXIF strip owned by prompt 16, duplicate-confirmation by prompt 08; live Supabase Storage BLOCKED here.
4. Next: prompt 05 (synthetic catalogue and demo fixtures).
5. Model/version: claude-opus-4-8[1m].

## 2026-10-17 - Prompt 05 (synthetic catalogue and demo fixtures)
1. Work: added tools/demo/build_scenarios.py (build_scenarios/validate_scenarios/render_nameplate) and tools/demo/render_assets.py; generated scenarios.json + 4 scenarios/*.json + nameplate PNG + cited evidence PDF + hash manifests. Added Pillow 12.1.1 to the workspace and re-locked. Scoped verify_kit markdown scan to skip uncommitted build dirs (.venv/node_modules/.git).
2. Verification (exit 0): `run_checks --prompt 05` → test_05.py PASS (9 tests); ruff clean; verify_kit PASSED; full regression prompts 00-05 all exit 0. Scenarios derived from real seed-42 records; DB ids == 1-based load ordinals; F02 rejections (incompatible expected part, unsupported stock claim) asserted; real PNG rendered.
3. Limits: base catalogue DB load (published catalogue_versions + immutable snapshot + evidence rows in one seeded transaction) and embedding (prompt 06) are BLOCKED here (no Postgres/BGE-M3).
4. Next: prompt 06 (extend legacy search).
5. Model/version: claude-opus-4-8[1m].

## 2026-10-17 - Prompt 06 (extend legacy search)
1. Work: characterized legacy identify/lexical/fulfilment; added internal-token route auth + /readiness (lexical vs semantic separate); added embedding_ingestion.embed_version (1024-d/unit-norm/NaN validation + source sha256 + model_revision, injected provider/store); fixed service.py margin-before-limit, NaN rejection, ADR-018 supersession terminal-fitment; extended partsiq_common.embeddings, repository, catalog embedder, search config/Dockerfile/requirements-embeddings (CPU wheel pins).
2. Verification (exit 0): run_checks --prompt 06 -> test_06.py PASS (10); isolated search suite PASS (71 incl. preserved legacy + F20..F34 offline via fake repo/encoder); 00-06 regression green; verify_kit PASSED; authored files ruff-clean (one pre-existing legacy E741 in test_fulfilment.py left untouched).
3. BLOCKED: live asyncpg/pgvector, real BGE-M3 weights, torch/sentence-transformers install (~2.5GB, disk 95% full), real published-version embedding.
4. Next: prompt 07 (authentication and demo sessions).
5. Model/version: claude-opus-4-8[1m].

## 2026-10-17 - Prompt 07 (authentication and demo sessions)
1. Work: added gateway auth.py (Supabase JWT verify via cached JWKS, refresh-once, DB-sourced roles, authenticate()), permissions.py (require_access mirroring RLS; assigned-only real review; own-active-demo; foreign->404), demo.py (create_demo rate-limit-before-DB; reset_demo idempotent generation increment). All dependency-injected.
2. Verification (exit 0): run_checks --prompt 07 -> test_07.py PASS (18) with a real RSA keypair/JWKS round-trip + fakes; ruff clean. Expired/wrong-issuer/wrong-audience/disallowed-alg/forged-role all rejected; unknown-kid refreshes once; access + demo flows asserted.
3. BLOCKED: live Supabase Auth, live DB (roles/sessions persistence, row-lock reset, job cancellation + storage cleanup). Full HTTP route wiring integrates at prompt 08 (owns api_v1).
4. Next: prompt 08 (enquiry intake and limits).
5. Model/version: claude-opus-4-8[1m].

## 2026-10-17 - Prompt 08 (enquiry intake and limits)
1. Work: added gateway enquiries.py (create_enquiry/add_message: canonical-hash idempotency, stale-revision 409, atomic commit via injected repo), uploads.py (confirm_upload: magic validation, duplicate idempotency, nonexistent 404), api_v1.py (v1 routes, bearer actor, 202-after-commit, error envelope). Modified rate_limit.py (fail-closed allow_within_limit adapter), config.py (Supabase/internal fields), main.py (register api_v1, requires_database=True, rate_allow).
2. Verification (exit 0): run_checks --prompt 08 -> test_08.py PASS (12); ruff clean. Idempotency same/different-payload, stale revision, rate-limit-before-DB, confirm magic/duplicate/nonexistent asserted.
3. BLOCKED: live DB atomic transaction (enquiry+message+revision+event), Redis limiter, Storage byte fetch; concrete DB repositories wired at runtime only.
4. Next: prompt 09 (deterministic durable workflow).
5. Model/version: claude-opus-4-8[1m].
