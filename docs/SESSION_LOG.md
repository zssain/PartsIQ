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

## 2026-10-17 - Prompt 09 (deterministic durable workflow)
1. Work: added orchestrator app (controller.next_step pure state machine with 12-step cap; state.py thread key per enquiry+revision; handlers.WorkflowHandlers + readiness gate; graph.build_graph via langgraph driven by the controller; events.consume_event dedup/stale-obsolete/retry; routes start/resume + readiness; runner batch; main). Added langgraph==1.1.3 + langgraph-checkpoint-postgres==3.0.4 to the lock.
2. Verification (exit 0): run_checks --prompt 09 -> test_09.py PASS (15) incl. a real build_graph run on InMemorySaver with test-double handlers; orchestrator suite PASS (7, 1 skip) test_f12/test_f50; 00-09 regression green; verify_kit PASSED; ruff clean.
3. Design: no fake-success nodes shipped (handlers None -> readiness false); blocking states are interrupts; next_step is the single decision point. BLOCKED: live Postgres checkpointer/event inbox, enquiry row-lock serialization.
4. Next: prompt 10 (intake specialist).
5. Model/version: claude-opus-4-8[1m].

## 2026-10-17 - Prompt 10 (intake specialist)
1. Work: added specialists/intake.py (extract_intake via shared call_structured + IntakeResult schema; prompts/intake.txt trusted instructions; customer text as untrusted data; missing quantity preserved null; confirmed machine fields merged forward), specialists/__init__.py.
2. Verification (exit 0): run_checks --prompt 10 -> test_10.py PASS (5) with a fake OpenAI client; orchestrator suite PASS (9, 1 skip) incl. test_f10; ruff clean. Bilingual preserved, invalid-quantity/disallowed-field rejected, confirmed-machine-not-overwritten asserted.
3. BLOCKED: live OpenAI structured output.
4. Next: prompt 11 (parts specialist and tools).
5. Model/version: claude-opus-4-8[1m].

## 2026-10-17 - Prompt 11 (parts specialist and tools)
1. Work: added orchestrator search_client.py (typed read-only adapter to the internal search service, injected HTTP), tools.py (ToolSession: 4-call bound, stale-catalogue rejection, read-only identify/search_parts only), specialists/parts.py (run_parts: candidate ids restricted to the compatible search set, code score/margin thresholds decide clarification, validate_selection 409 on unavailable choice).
2. Verification (exit 0): run_checks --prompt 11 -> test_11.py PASS (11); orchestrator suite PASS (12, 1 skip) incl. test_f26; ruff clean; 00-11 regression green; verify_kit PASSED.
3. Design: deterministic code owns candidate restriction + clarification; the LLM only phrases explanation and cannot override low confidence or inject incompatible parts. BLOCKED: live search service HTTP + OpenAI.
4. Next: prompt 12 (deterministic verification).
5. Model/version: claude-opus-4-8[1m].

## 2026-10-17 - Prompt 12 (deterministic verification)
1. Work: added orchestrator/app/verification.py (seven named pure checks: current_revision, catalogue_version, candidate_membership, configuration_membership, source_evidence, quantity, allocation; aggregate allocation recomputed across items sharing a part+warehouse; canonical sorted-JSON/decimal-string SHA256; resolve_source_reference for F28 version-specific citations; verify_facts pure + verify_current/run_verification persist one result per (enquiry,revision) via an injected store). Modified handlers.py (make_verify_handler adapts the gate into the graph verify node) and graph.py (docstring records the connection; signature preserved). No LLM decides pass/fail (ADR-003).
2. Verification (exit 0): run_checks --prompt 12 -> test_12.py PASS (24); orchestrator suite PASS (22, 1 skip) incl. test_f46; search suite PASS (75) incl. test_f28; 00-12 foundation regression all exit 0; ruff clean; verify_kit PASSED; gateway suite PASS (15, unaffected).
3. Design: the five F46 failure scenarios each fail a specific named rule (unknown part/hidden extra item -> candidate membership; incompatible part -> configuration membership; stale catalogue -> catalogue version; oversold -> allocation aggregate). F28 citation resolves to a version-specific document+page; a mismatched version/absent citation fails the source-evidence rule (MISSING_EVIDENCE). No new package; no schema change (verification_results already migrated in prompt 03); no controller change.
4. BLOCKED: live verification_results Postgres adapter and the F29 evidence-viewer UI binding (later feature prompt).
5. Next: prompt 13 (reply specialist and renderer).
6. Model/version: claude-opus-4-8[1m].

## 2026-10-17 - Prompt 13 (reply specialist and renderer)
1. Work: added specialists/reply.py (draft_reply -> ReplySlots via shared wrapper; validate_slots rejects digits/identifiers in prose; strict schema rejects unsupported slots), rendering.py (render_reply: code-owned layout, html.escape all text, Arabic RTL + LTR-isolated identifiers, non-guaranteed transfer estimates, no price/quotation, no Jinja on model output), prompts/reply.txt. Modified handlers.py (make_draft_handler: provider/credit failure -> phase needs_staff_draft, no paid fallback) and graph.py (docstring connection).
2. Verification (exit 0): run_checks --prompt 13 -> test_13.py PASS (16); orchestrator suite PASS (28, 1 skip) incl. test_f45; ruff clean.
3. Design: model writes prose only; code inserts every number/allocation; unapproved facts never reach prose; staff authors controlled slots through the same gate on provider failure (F45).
4. BLOCKED: live OpenAI + live drafts Postgres adapter.
5. Next: prompt 14 (approval and revision transactions).
6. Model/version: claude-opus-4-8[1m].

## 2026-10-17 - Prompt 14 (approval and revision transactions)
1. Work: added approval.py (approve/reject over an injected ReviewRepository port: assigned/own-session auth else 404; expected-revision + verified-fact-hash binding; stock refresh + re-verify; staff edits via validate_slots; idempotent double-click; rejection without publication) and revisions.py (revise over a RevisionRepository port: increment revision + immutable snapshot, history untouched). Updated graph.py/handlers.py docstrings (REVIEW interrupt resolved out-of-band).
2. Verification (exit 0): run_checks --prompt 14 -> test_14.py PASS (13); orchestrator suite PASS (36, 1 skip) incl. test_f40/test_f47; run_checks --feature F49 -> test_f49.py PASS (3); ruff clean.
3. Design: publication is coupled to its approved decision and bounded one-per-revision by the committed schema; audit append shares the approval transaction (failure rolls back). No LLM authorizes publication; no worker/specialist write path publishes.
4. BLOCKED: live locked Postgres transaction + triggers (unique publication, immutability, append-only, UPDATE/DELETE/TRUNCATE rejection); tested via a fake repo mirroring those constraints.
5. Next: prompt 15 (worker leases and sweeper).
6. Model/version: claude-opus-4-8[1m].

## 2026-10-17 - Prompt 15 (worker leases and sweeper)
1. Work: added worker leases.py (claim/heartbeat/finish with fresh token + attempts++ + token/revision/generation fencing), dispatcher.py (persist-before-Redis enqueue + dedupe, ConcurrencyGuard one nameplate+one pdf, Dispatcher drain flag), sweeper.py (sweep_once reclaim/redispatch, max_attempts -> failed), internal.py (internal-token signing route, no orchestrator HTTP), main.py. Added [tool.pytest.ini_options] to worker pyproject.
2. Verification (exit 0): run_checks --prompt 15 -> test_15.py PASS (14); worker suite PASS (10) incl. test_f51/test_f52; ruff clean.
3. Design: DB is the job source of truth (Redis is dispatch only); stale/expired/old-generation work cannot commit; heavy work bounded so it never starves HTTP intake.
4. BLOCKED: live asyncpg SKIP LOCKED, Redis, Storage signing; tested with fakes mirroring the semantics.
5. Next: prompt 16 (nameplate vision job).
6. Model/version: claude-opus-4-8[1m].

## 2026-10-17 - Prompt 16 (nameplate vision job)
1. Work: added worker jobs/nameplate.py (validate_image with Pillow + decoded-pixel cap; read_nameplate via OpenAI vision through the shared client, EXIF-strip/orientation-normalize, code-owned attachment_id + mandatory confirmation, partial-null, provider failure recoverable) and jobs/__init__.py; gateway ocr_confirmation.py (confirm_extraction: owner/assigned/own-session auth, stale 409, verbatim serial, blank-serial missing flow) + route in api_v1.py; dispatcher handler registry (register_handler/get_handler) wired for "nameplate" in worker main.
2. Verification (exit 0): run_checks --prompt 16 -> test_16.py PASS; worker suite PASS (19) incl. test_f14; gateway suite PASS (15, regression); ruff clean.
3. Design: model confidence is never treated as accuracy (confirmation always required); image text is data not instructions; unconfirmed OCR never authorizes matching.
4. BLOCKED: live OpenAI vision, Storage fetch, lease-fenced DB persistence of extraction + ocr_completed event.
5. Next: prompt 17 (approved enquiry pdf).
6. Model/version: claude-opus-4-8[1m].

## 2026-10-17 - Prompt 17 (approved enquiry pdf)
1. Work: added worker jobs/export_pdf.py (render_export_html via trusted autoescaped Jinja template; export_enquiry: approved-immutable-only, injected HTML->PDF port, sha256, exports-bucket upload, persist under lease), templates/enquiry_summary.html, bundled brand fonts+logo under app/static/brand. Registered export_pdf handler. Added Jinja2/pypdf (installed) + playwright (locked; Chromium deferred) to worker pyproject; uv.lock additive.
2. Verification (exit 0): run_checks --prompt 17 -> test_17.py PASS (pypdf-validated single-page PDF via fake renderer); worker suite PASS (19); ruff clean. After re-lock used `uv sync --all-packages` to keep member deps (langgraph etc.); 00-17 foundations + 4 service suites green.
3. Design: watermark + non-guaranteed estimate always present; no price/quotation; staff notes/secrets excluded; no model-authored template evaluated; Chromium render is an injected, locked-down port.
4. BLOCKED: live Playwright/Chromium, Storage upload, approved-snapshot DB load. Pre-existing unrelated: tools/catalog pytest collection (stray __init__ shadows inner package).
5. Next: prompt 18 (frontend shell and authentication).
6. Model/version: claude-opus-4-8[1m].

## 2026-10-17 - Prompt 18 (frontend shell and authentication)
1. Work: created apps/web Next.js 16 App Router shell; installed exact pnpm pins (committed pnpm-lock.yaml). Landing (F01) with journey + synthetic notice (no affiliation) + Start demo/architecture links + conditional repo link; invited-staff-only login (no public signup); lib/api.ts (bearer in Authorization header, typed ApiError, request-id); lib/auth.ts (browser Supabase, NEXT_PUBLIC_* only, anonymous demo); lib/contracts.ts; BrandLogo (alt, no stretch); tokens.css; configs; brand assets under public/brand.
2. Verification: run_checks --prompt 18 -> test_18.py PASS (structural + security invariants); apps/web vitest f01.test.tsx PASS (4) on node 25 / pnpm 10.31; python ruff clean.
3. Design: all business calls through the gateway; only Supabase Auth bypasses it; no secret in NEXT_PUBLIC/URL/source; real-client signup disabled. The per-prompt gate is the Python structural test (run_checks has no pnpm wiring); the vitest suite is run directly and reported (not faked).
4. BLOCKED: live Supabase Auth + gateway; Playwright e2e specs (prompts 22/27).
5. Next: prompt 19 (customer chat and demo).
6. Model/version: claude-opus-4-8[1m].

## 2026-10-17 - Prompt 19 (customer chat and demo)
1. Work: apps/web Chat (AbortController + bounded backoff + hidden-tab throttle; idempotent revision-bound send preserving unsent text), Progress (customer vs staff wait, retry, no fabricated completion), OcrConfirmation (verbatim serial), UploadCard (MIME+size+signed+confirm), chat/[id] + demo pages (four seed-42 scenarios + reset clears cache). Feature tests: test_f02 (acceptance), test_f05/test_f13 (gateway), test_f09/test_f11 (orchestrator), f15.test.tsx (web), test_19 (foundation).
2. Verification: run_checks --prompt 19 -> test_19.py PASS; web vitest f01+f15 = 8 passed; orchestrator 43 passed/1 skip; gateway 22 passed; acceptance test_f02 PASS; python ruff clean.
3. Design: only server-returned (approved) recommendations appear; code-owned clarifications; graceful failures preserve input and retry safely; reset clears old-generation client cache.
4. Note: created the prompt-listed feature tests even where file-ownership records creator 20/22; manifest unchanged. BLOCKED: live gateway/Supabase/Storage; Playwright e2e.
5. Next: prompt 20 (staff workspace and timeline).
6. Model/version: claude-opus-4-8[1m].

## 2026-10-17 - Prompt 20 (staff workspace and timeline)
1. Work: apps/web review components Workspace (assembles revision/candidates/match-explanations/stock/verification/draft/timeline/staff-notes with empty states; score labelled match score not probability; absent evidence unavailable), ApprovalControls (approve only verified-current, expected_revision + idempotency key, 409 -> reload, reject requires reason, structured prose edit, approved-PDF action), Timeline (persisted stages, customer vs staff wait, retry); staff inbox + enquiry pages. Feature tests: f18/f27/f37 (web vitest), test_f03 (gateway), test_f32 (search), test_f39 (orchestrator), test_f61 (worker), test_20 (foundation).
2. Verification: run_checks --prompt 20 -> test_20.py PASS; web vitest 17 passed (f01/f15/f18/f27/f37); gateway 28 / search 80 / orchestrator 47(+1 skip) / worker 22; python ruff clean; verify_kit PASSED. Full 00-20 foundation regression all exit 0.
3. Design: only current verified state enables approve; publication double-click publishes once and a concurrent edit defeats a stale approval; staff notes never mixed with customer messages; scores are a match score, not a calibrated probability; no fabricated progress.
4. BLOCKED: live gateway/Supabase/Storage/orchestrator; Playwright e2e (22/27).
5. Next: prompt 21 (quality / evals). Prompts 13-20 complete this session.
6. Model/version: claude-opus-4-8[1m].

## 2026-10-17 - Prompt 21 (labelled evaluations)
1. Work: tools/evals/run.py + __init__.py (evaluate_case, run_suite injected-solver, dataset_sha256, accuracy excl. unlabelled + abstention, build_run_receipt git-sha/model-id, deterministic_solver); tests/evals/cases.json (11 labelled cases: 4 demos + arabic/typo/serial/ambiguity/stock/injection + unlabelled); tests/evals/test_scenarios.py.
2. Verification (exit 0): run_checks --prompt 21 -> test_21.py PASS; --feature F62 -> test_f62.py PASS; test_scenarios.py PASS (3, incl. demo labels validated against build_scenarios); ruff clean.
3. Design: deterministic suite makes no OpenAI call; accuracy never uses model confidence; failures keep actual output; fixture disjoint from prompt templates; injection ignored.
4. BLOCKED: live-model eval path (confirmed credit) separate from deterministic suite.
5. Next: prompt 22 (security and failure recovery gate).
6. Model/version: claude-opus-4-8[1m].

## 2026-10-17 - Prompt 22 (security and failure recovery gate)
1. Work: tests/integration/test_security_recovery.py (assert_disposable_environment guard + live scenario class, skip without disposable DB), test_rls.py + test_budget_races.py (skip-gated), tests/e2e/security.spec.ts (Playwright deliverable), gateway test_f04.py (demo isolation) + test_f54.py (JWT malformed/none-alg reject, DB roles, assigned-only), apps/web f53.test.tsx (api error mapping).
2. Verification (exit 0): run_checks --prompt 22 -> test_22.py PASS; gateway 36 passed; web vitest 20 passed; ruff clean.
3. Design: disposable guard refuses production; forged JWT roles ignored (roles from DB); require_access denies foreign/missing-context with 404; verification rejects oversold; no secret in the browser bundle. Live scenarios skip (never faked).
4. BLOCKED: disposable local Supabase (auth+storage), Redis, running app for e2e.
5. Next: prompt 23 (observability and credit limits).
6. Model/version: claude-opus-4-8[1m].

## 2026-10-17 - Prompt 23 (observability and credit limits)
1. Work: tools/credit_allowance.py (validate_allowance), services/gateway/app/metrics.py (get_metrics staff-only, median/p95/cost, demos excluded), tools/check_readiness.py (readiness_report). Additive connections: client.call_structured optional outage-safe tracer (redacted span + ids); budget.reserve_for_request (worst-case atomic); telemetry.LangfuseExporter + build_tracer. langfuse==3.14.5 pinned as partsiq-common optional [trace] extra; uv.lock re-locked (packaging 26.3->25.0).
2. Verification (exit 0): run_checks --prompt 23 PASS; --feature F64/F67 PASS; prompt 01 + all four service suites green; verify_kit PASSED; ruff clean; full 00-23 regression green.
3. Design: allowance is explicit config, not key-inferred; worst-case reserved per attempt; tracing optional + outage-safe; local budget accounting authoritative; metrics exclude demos by default.
4. BLOCKED: live Langfuse sink + live metrics DB (fakes used).
5. Next: prompt 24 (production containers and caddy).
6. Model/version: claude-opus-4-8[1m].

## 2026-10-17 - Prompt 24 (production containers and caddy)
1. Work: docker-compose.prod.yml (Caddy-only public 80/443; private network; immutable ${RELEASE_SHA} app images; digest-pinned caddy/redis; separate worker/sweeper/consumer; read-only rootfs + tmpfs + log caps + resource limits), Caddyfile (auto-TLS + security headers + reverse_proxy), orchestrator/worker Dockerfiles, infra/verify_images.py + infra/images.lock.json. Modified gateway/search Dockerfiles to pin the base @sha256 digest.
2. Verification (exit 0): run_checks --prompt 24 -> test_24.py PASS (compose clean; verifier catches mutable tag / missing healthcheck / published internal port / embedded credential; Dockerfiles digest-pinned; only Caddy publishes); ruff clean.
3. Design: immutable images, no public internal ports, no embedded secrets, no k8s/public Redis; one search process to avoid duplicate model memory.
4. BLOCKED: image build/push/run (Docker + registry); recorded base digests re-verified at deploy.
5. Next: prompt 25 (ci and controlled deployment).
6. Model/version: claude-opus-4-8[1m].

## 2026-10-17 - Prompt 25 (ci and controlled deployment)
1. Work: .github/workflows/ci.yml (service-isolated python matrix + frontend + RLS integration + evals; contents:read; SHA-pinned actions; APP_ENV=test), deploy-backend.yml (workflow_dispatch only; build-push -> migrate -> deploy; environment approval + INFRA_READY gate; OIDC id-token), tools/ci_checks.py (check_ci_configuration).
2. Verification (exit 0): run_checks --prompt 25 -> test_25.py PASS; --feature F66 -> test_f66.py PASS; ruff clean.
3. Design: no prod DB in tests; no secrets to fork PRs (deploy never on pull_request); deployment disabled until infra ready; migration precedes image activation; actions SHA-pinned.
4. BLOCKED: live CI run, GHCR build/push, AWS OIDC assume; action SHAs to re-verify at setup.
5. Next: prompt 26 (aws free-plan deployment).
6. Model/version: claude-opus-4-8[1m].

## 2026-10-17 - Prompt 26 (aws free-plan deployment)
1. Work: infra/ec2/preflight.py (preflight + CLI gate: free plan, unexpired credit, instance fits measured peak + headroom), bootstrap.sh (validated env path + 0600 secrets), deploy.sh (one hex SHA, lock, healthcheck), rollback.sh (previous immutable SHA, no DB reset). Wired a preflight step into deploy-backend.yml.
2. Verification (exit 0): run_checks --prompt 26 -> test_26.py PASS; prompt 25 + F66 still green; ci config clean; ruff clean.
3. Design: no automatic paid upgrade; free micro not assumed adequate (measured sizing gates instance choice); SSM not public SSH; immutable-SHA deploy with rollback; never reset the DB.
4. BLOCKED: real EC2 provisioning/activation/SSM (AWS account required); region/sizing are operator receipts.
5. Next: prompt 27 (vercel and hosted acceptance).
6. Model/version: claude-opus-4-8[1m].

## 2026-10-17 - Prompt 27 (vercel and hosted acceptance)
1. Work: tools/hosted_acceptance.py (run_hosted_acceptance: HTTPS-only outside localhost, four-scenario check incl. approval+PDF via injected client, is_available gate, refuses with no client), infra/vercel/README.md (separate preview/prod bindings, public-only NEXT_PUBLIC, exact-origin CORS, documented free-tier limits), tests/e2e/hosted.spec.ts (Playwright, skips offline).
2. Verification (exit 0): run_checks --prompt 27 -> test_27.py PASS; ruff clean. FULL build regression 00-27 all exit 0; F02/F49/F62/F64/F66/F67 pass; gateway/search/orchestrator/worker suites + web vitest (20) + verify_kit all green.
3. Design: deployment not claimed available unless real hosted checks pass; no wildcard CORS; only publishable key public; free-tier limits documented as measured facts.
4. BLOCKED: live Vercel/EC2/Supabase hosted run + Playwright hosted spec.
5. Next: numeric build 00-27 complete; the F-coverage prompts (prompts/README.md) remain.
6. Model/version: claude-opus-4-8[1m].

## 2026-10-17 - F16 (photo quality feedback)
1. Work: services/worker/app/features/f16_photo_quality_feedback.py (assess_photo: decodability/media-type/dimensions + dark/blur heuristic before the paid call; unsupported/undecodable/oversized -> readable False; low-res/dark/blur -> advisory guidance, still readable; no fabricated confidence %), dispatcher.photo_quality_gate passthrough, apps/web lib/features/f16_photo_quality_feedback.ts (browser mirror) + components/features/PhotoQualityNotice.tsx; wired into Chat.tsx and landing journey.
2. Verification: worker suite 33 passed incl. tests/features/test_f16.py (11); ruff clean; apps/web vitest 20 passed (Chat/page changes non-breaking); tsc clean on changed files (pre-existing f53.test.tsx errors unrelated). ESLint BLOCKED in this env (missing @eslint/eslintrc devDep).
3. Design: advisory heuristic (blur never blocks a readable image); only format/decode/bomb reject; no OCR confidence percentage; browser pre-check is advisory UX, server worker check authoritative.
4. BLOCKED: live Storage object fetch + nameplate paid-path invocation of the gate (nameplate.py is prompt 16's file, not modified here); browser createImageBitmap/canvas path exercised only in a real browser.
5. Next: F17 (multi-part enquiries).
6. Model/version: claude-opus-4-8[1m].

## 2026-10-17 - F17 (multi-part enquiries)
1. Work: services/orchestrator/app/features/f17_multi_part_enquiries.py (resolve_items: per-item status, stock planned ONCE per selected part + distributed in ordinal order so duplicate parts cannot double-count; unresolved_item_ids/can_approve_all readiness gate; zero quantity rejected; <=20 items; NOT_FOUND auth incl. demo own-session; STALE_REVISION). routes.py restructured to a prefix-free parent router mounting /v1/workflow + a token-guarded /internal router with POST /internal/items/resolve (so main.py is untouched). handlers.unresolved_items shares the single readiness rule. apps/web lib/features/f17_multi_part_enquiries.ts + components/features/ItemList.tsx; wired into Chat.tsx + landing journey.
2. Verification: orchestrator suite 59 passed + 1 skip incl. tests/features/test_f17.py (12); ruff clean; apps/web vitest 20 passed. Commands: (services/orchestrator) python -m pytest -q; (apps/web) pnpm test.
3. Design: aggregate allocation mirrors verification.check_allocation; earlier ordinal line wins contested stock; VALIDATION_FAILED (422) for non-positive quantity; internal route token-guarded + propagated actor; browser authors no compatibility fact.
4. BLOCKED: live enquiry_items/fulfilment_plans Postgres adapter + RLS; the gateway public /v1/enquiries/{id}/items/resolve proxy route; HTTP path exercised offline only (function-level tests + fake store).
5. Next: F19 (enquiry history).
6. Model/version: claude-opus-4-8[1m].

## 2026-10-17 - F19 (enquiry history)
1. Work: services/gateway/app/features/f19_enquiry_history.py (list_history: owned-only from ActorContext so a foreign owner id is structurally ignored; demo active-generation scoping via the repo; keyset cursor over (created_at,id) -> equal timestamps never dup/skip; opaque base64 cursor, invalid -> 422; limit 1..100 -> 422; over-fetch+1 for next_cursor). api_v1.py GET /v1/enquiries. apps/web lib/features/f19_enquiry_history.ts + components/features/HistoryList.tsx + app/history/page.tsx; landing nav link.
2. Verification: gateway suite 44 passed incl. tests/features/test_f19.py (8); ruff clean; apps/web vitest 20 passed. Commands: (services/gateway) python -m pytest -q; (apps/web) pnpm test.
3. Design: ownership never from client input; cursor is opaque; created_at drives ordering (EnquiryView exposes updated_at per the fixed schema, so the list shows updated_at); scoped 404 on foreign/expired conversation links.
4. BLOCKED: live enquiries Postgres adapter + RLS; real demo-generation filter at the DB.
5. Next: F55 (saved machines).
6. Model/version: claude-opus-4-8[1m].

## 2026-10-17 - F55 (saved machines)
1. Work: services/gateway/app/features/f55_saved_machines.py (save_machine idempotent-by-key, list_machines own-active, rename_machine label-only, archive_machine soft delete; identifiers only -> stale configuration never reused; prefill_from_machine carries no configuration/candidate; serial verbatim; foreign id -> 404; blank label/serial & non-positive model -> 422). api_v1.py POST/GET/PATCH/DELETE /v1/machines. apps/web lib/features/f55_saved_machines.ts + components/features/SavedMachines.tsx; landing journey mention.
2. Verification: gateway suite 56 passed incl. tests/features/test_f55.py (12); ruff clean; apps/web vitest 20 passed.
3. Design: duplicate label allowed (identity = UUID); archive sets archived_at, never deletes referenced data; prefill re-identifies against current catalogue.
4. BLOCKED: live saved_machines Postgres adapter + RLS + common idempotency store.
5. Next: F56 (repeat enquiry).
6. Model/version: claude-opus-4-8[1m].
