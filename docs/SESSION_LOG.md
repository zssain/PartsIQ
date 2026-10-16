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
