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

Completed through 11 (offline-faithful; live infra BLOCKED and reported, never faked):
- 07 gateway auth.py/permissions.py/demo.py (Supabase JWT via cached JWKS refresh-once, DB-sourced roles, assigned-only review, idempotent demo reset) — test_07 PASS (18, real RSA/JWKS round-trip).
- 08 gateway enquiries.py/uploads.py/api_v1.py (canonical-hash idempotency, stale-revision 409, confirm magic/duplicate/404, 202-after-commit) — test_08 PASS (12).
- 09 orchestrator controller.next_step + graph (langgraph) + events.consume_event + handlers/state/routes/runner/main — test_09 PASS (15, real build_graph on InMemorySaver); orchestrator suite PASS.
- 10 orchestrator specialists/intake.extract_intake (strict IntakeResult, missing-quantity null, confirmed-field merge) — test_10 PASS (5).
- 11 orchestrator specialists/parts.run_parts + tools.ToolSession + search_client (compatible-only candidates, code thresholds, 4-call bound, stale-version reject, 409 on unavailable choice) — test_11 PASS (11).
- Added langgraph 1.1.3 + langgraph-checkpoint-postgres 3.0.4 to the lock. Full regression run_checks --prompt 00..11 all exit 0; verify_kit PASSED.
- BLOCKED throughout: live Supabase Auth/DB/RLS, Redis, pgvector + BGE-M3 (torch not installed), live OpenAI, Postgres LangGraph checkpointer. Concrete DB/HTTP wiring for runtime is deferred to where its service exists.

Completed through 12 (Deterministic verification):
- orchestrator/app/verification.py: seven NAMED pure checks (current_revision, catalogue_version, candidate_membership, configuration_membership, source_evidence, quantity, allocation) over typed (VerifiedFacts, VerificationEvidence). Aggregate allocation recomputed across all items sharing a (part, warehouse) so an oversold plan split across items is caught. Canonical fact hash = SHA256 over sorted JSON with Decimals rendered as decimal strings and item/allocation lists ordered (stable, order-independent). verify_facts (pure) + verify_current/run_verification persist exactly one result per (enquiry, revision) through an injected store. resolve_source_reference parses the version-specific catalogue citation (F28). No LLM in the pass/fail path (ADR-003).
- Failure codes map: unknown part->INCOMPATIBLE (candidate membership), hidden extra item->UNRESOLVED_ITEM, incompatible part->INCOMPATIBLE (configuration membership), stale catalogue->STALE_CATALOGUE, stale revision->STALE_REVISION, oversold->OVERALLOCATION, missing stock->STALE_STOCK, inconsistent/absent shortage or non-positive quantity->INVALID_QUANTITY, missing/mismatched citation->MISSING_EVIDENCE.
- Wiring: handlers.make_verify_handler(store) adapts the gate into the graph verify node (sets verification_id + phase "verified", routes to human review); graph.py docstring records the connection. No controller change; build_graph signature preserved.
- Verification (exit 0): run_checks --prompt 12 -> test_12.py PASS (24); orchestrator suite PASS (22, 1 skip) incl. test_f46; search suite PASS (75) incl. test_f28; 00-12 regression all exit 0; ruff clean; verify_kit PASSED; gateway suite PASS (15, unaffected).
- BLOCKED (reported, not faked): the live verification_results Postgres adapter (UNIQUE(enquiry_id,revision)) and the F29 evidence-viewer UI binding (a later feature prompt) remain integration work; tested here only through an in-memory store + typed fixtures.

Completed through 13 (Reply specialist and renderer):
- orchestrator/app/specialists/reply.py: draft_reply fills ONLY ReplySlots (greeting/explanation/closing) via the shared call_structured wrapper with a fact-free brief; validate_slots rejects any slot carrying a digit (ASCII/Arabic-Indic) or identifier-looking token, and the strict schema rejects unsupported slots. prompts/reply.txt instructs prose-only, no numbers/identifiers/prices.
- orchestrator/app/rendering.py: render_reply builds the message in code — greeting/explanation + code-owned part/quantity/warehouse/estimate lines + closing. All text html.escape'd (F27); Arabic RTL with identifiers in LTR <bdi>; transfer times labelled non-guaranteed estimates; no price/quotation wording. No Jinja is evaluated on model output.
- handlers.make_draft_handler wires it into the graph draft node; a provider/credit failure routes to phase "needs_staff_draft" (staff authors controlled slots through the same validate_slots gate) — no paid fallback, no faked prose (ADR-015/F45). graph.py docstring records the connection; build_graph signature preserved.
- Verification (exit 0): run_checks --prompt 13 -> test_13.py PASS (16); orchestrator suite PASS (28, 1 skip) incl. test_f45; ruff clean.
- BLOCKED: live OpenAI structured output and the live drafts Postgres adapter (UNIQUE(enquiry_id,revision)); tested here with a fake client + in-memory store.

Completed through 14 (Approval and revision transactions):
- orchestrator/app/approval.py: approve/reject over an injected ReviewRepository port (the locked single transaction). Enforces assigned-reviewer/own-demo-session authorization (else 404), expected-revision match, draft-id match, binding to the verified fact hash (canonical_facts_sha256), stock refresh + re-verification (changed plan blocked), staff prose edits through validate_slots, and idempotent replay (double-click publishes once; key reuse with a different payload -> IDEMPOTENCY_MISMATCH). reject records a reason and never publishes.
- orchestrator/app/revisions.py: revise over a RevisionRepository port; owner/assigned/own-session authorization, expected-revision check, then increment revision + immutable snapshot + status processing (historical approval never mutated, F40).
- Publication coupling and one-recommendation-per-revision are enforced by the committed schema (messages CHECK + messages_one_publication_idx, review_decisions_idempotency_idx); audit append is in the same transaction and its failure rolls back the approval. graph.py/handlers.py docstrings record that the REVIEW interrupt is resolved out-of-band by these route-invoked services.
- Verification (exit 0): run_checks --prompt 14 -> test_14.py PASS (13); orchestrator suite PASS (36, 1 skip) incl. test_f40/test_f47; run_checks --feature F49 -> tests/acceptance/test_f49.py PASS (3); ruff clean.
- BLOCKED: the live locked Postgres transaction, the unique-publication/immutability/append-only triggers and application-role UPDATE/DELETE/TRUNCATE rejection are integration-only; tested here with a fake repository that mirrors those constraints.

Completed through 15 (Worker leases and sweeper):
- worker/app/leases.py: claim_job (fresh fencing token + attempts++), heartbeat (renew while token ours), finish_job (fenced by token AND current enquiry revision/session generation — a stale revision or old demo generation cannot commit, F52/F05). worker/app/dispatcher.py: persist-before-Redis enqueue_job (dedupe_key idempotent; push failure tolerated), ConcurrencyGuard (one nameplate + one export_pdf), Dispatcher drain flag for graceful shutdown. worker/app/sweeper.py: sweep_once reclaims pending/expired jobs and redispatches; a job past max_attempts is failed not retried. worker/app/internal.py: single internal-token-guarded storage sign-download route (Docker-network only; no orchestrator HTTP). worker/app/main.py: service app (readiness false until store+queue wired).
- All DB/Redis/Storage I/O is behind injected ports; worker pyproject gained [tool.pytest.ini_options] for the isolated suite. No new package (redis/asyncpg live adapters are BLOCKED).
- Verification (exit 0): run_checks --prompt 15 -> test_15.py PASS (14); worker suite PASS (10) incl. test_f51/test_f52; ruff clean.
- BLOCKED: live asyncpg (FOR UPDATE SKIP LOCKED), Redis queue, Storage signing; tested with fake store/queue that mirror the locking/fencing/dedupe semantics.

Completed through 16 (Nameplate vision job):
- worker/app/jobs/nameplate.py: validate_image (Pillow decode, media-type match, MAX_DIMENSION + 40 MP decoded-pixel cap, sha256) and read_nameplate (EXIF-stripped/orientation-normalized/bounded image to OpenAI vision via the shared client; extracts model_text/serial_text/issues only; code forces the authoritative attachment_id and confirmation_required=True — model confidence is never accuracy, ADR-013; partial fields stay null; provider/budget failure raises a recoverable error). Prompt isolation: image text is data, never instructions.
- gateway/app/ocr_confirmation.py: confirm_extraction (owner/assigned/own-session auth else 404; expected-revision stale -> 409; serial stored verbatim so leading zeros survive; blank corrected serial -> missing-serial flow). Registered POST /v1/enquiries/{id}/extractions/{extraction_id}/confirm in api_v1.py.
- dispatcher gained a job-kind handler registry (register_handler/get_handler); worker main registers "nameplate".
- Verification (exit 0): run_checks --prompt 16 -> test_16.py PASS; worker suite PASS (19) incl. test_f14; gateway suite PASS (15, regression); ruff clean.
- BLOCKED: live OpenAI vision, Storage object fetch, DB persistence of the extraction + ocr_completed workflow event (the lease-fenced write path from prompt 15). Tested with a fake vision client, real in-memory Pillow images, and fake repos.

Completed through 17 (Approved enquiry PDF):
- worker/app/jobs/export_pdf.py: render_export_html fills a TRUSTED, code-owned Jinja template (autoescape on; only the already-escaped reply is |safe) — logo, bilingual text, verified selections, references/citations, synthetic-demo watermark, non-guaranteed-estimate note, long names wrap (word-break), no price/quotation wording. export_enquiry refuses anything but an approved immutable revision, renders via an injected HTML->PDF port, hashes the bytes, uploads to the exports bucket and persists the export record under the lease. templates/enquiry_summary.html + bundled brand fonts/logo under app/static/brand (verified vs SHA256SUMS). Worker registers the "export_pdf" handler.
- Packages: `uv pip install Jinja2==3.1.6 pypdf==6.8.0` (used offline); playwright==1.58.0 pinned in worker pyproject and locked, but its Chromium browser binary is a deferred/BLOCKED download (deployment image, prompt 24) — the Chromium render is the injected port. uv.lock change is purely additive (jinja2, markupsafe, pypdf, playwright, pyee, greenlet).
- Verification (exit 0): run_checks --prompt 17 -> test_17.py PASS (incl. a pypdf-validated single-page PDF through the fake renderer); worker suite PASS (19); ruff clean.
- Env note: this workspace has members whose deps are not reachable from the root project, so use `uv sync --all-packages` (a bare `uv sync` prunes orchestrator/worker deps like langgraph). The venv is currently complete; all 00-17 foundations + gateway/search/orchestrator/worker suites pass. Pre-existing/unrelated: the tools/catalog pytest suite fails to collect due to a stray tools/catalog/__init__.py shadowing the inner `catalog` package (owned by prompt 00; not exercised by the per-prompt gate) — left untouched.
- BLOCKED: live Playwright/Chromium PDF rendering, Storage upload, approved-snapshot DB load.

Completed through 18 (Frontend shell and authentication):
- apps/web Next.js 16 App Router shell created and the exact pnpm pins installed (next 16.2.12, react 19.2.6, @supabase/ssr 0.8.0, tailwindcss 4.1.18, vitest 4.1.11, …) → committed apps/web/pnpm-lock.yaml. Files: tsconfig/next.config/postcss/eslint/vitest configs, app/layout.tsx, app/page.tsx (F01 landing: journey, synthetic-demo notice with no affiliation claim, Start demo + architecture links, repo link hidden when NEXT_PUBLIC_REPO_URL unset), app/login/page.tsx (invited-staff only; no public signup), styles/tokens.css (navy/gold), lib/api.ts (typed ApiError, bearer in Authorization header NOT the URL, request-id surfaced), lib/auth.ts (browser Supabase with only NEXT_PUBLIC_* values; anonymous demo; staff password), lib/contracts.ts (TS mirrors), components/BrandLogo.tsx (meaningful alt, no stretch), tests/setup.ts, playwright.config.ts. Brand PNG/font assets copied under apps/web/public/brand.
- Verification: run_checks --prompt 18 -> tests/foundations/test_18.py PASS (structural: pins, required files, bearer-not-URL, only public Supabase values, no secret in apps/web, no public signup, synthetic notice, conditional repo link, logo alt). apps/web vitest: tests/features/f01.test.tsx PASS (4) via the installed toolchain (node 25 / pnpm 10.31). Python ruff clean.
- Note: run_checks has no pnpm wiring, so the per-prompt gate is the Python structural test; the vitest suite is run directly and reported here (it passes, not faked). node_modules/.next are gitignored.

Completed through 19 (Customer chat and demo):
- apps/web components: Chat.tsx (AbortController + bounded exponential backoff polling with hidden-tab throttle; send is idempotency-keyed + revision-bound and preserves unsent text on failure; React escapes message text), Progress.tsx (persisted stages only, waiting-customer vs waiting-staff, retry on failed poll — no fabricated completion), OcrConfirmation.tsx (serial kept verbatim incl. leading zeros, confirm/correct, {extraction,onConfirm} contract + extractionId/expectedRevision plumbing), UploadCard.tsx (MIME allowlist + 10 MB cap + signed upload + confirm), app/chat/[id]/page.tsx, app/demo/page.tsx (four seed-42 scenario cards + reset that clears client cache).
- Verification: run_checks --prompt 19 -> tests/foundations/test_19.py PASS (structural + invariants). apps/web vitest: f01 + f15 = 8 passed. Cross-service feature tests PASS in their suites: orchestrator test_f09 (bilingual intake) + test_f11 (clarifications) -> orch 43 passed/1 skip; gateway test_f05 (demo reset idempotency) + test_f13 (upload magic/duplicate/404) -> gateway 22 passed; acceptance test_f02 (four seed-42 scenarios + reject incompatible/unsupported) PASS. Python ruff clean.
- Note: prompt 19's FILES TO CREATE lists test_f02/f05/f09/f11/f13 (created here); spec/file-ownership.json records some of those creators as 20/22 — followed the prompt, manifest left unchanged. These feature tests exercise entry points built in earlier prompts (05/07/08/10/11).
- BLOCKED: live gateway/Supabase/Storage; Playwright e2e (22/27).

Completed through 20 (Staff workspace and timeline):
- apps/web review components: Workspace.tsx (assembles the current snapshot — revision badge, candidates with evidence-derived match explanations + "Match score" label (never a probability), warehouse stock available/warehouse/timestamp, named verification results, draft, timeline, staff-only notes kept separate from customer messages; explicit empty states; absent evidence shown unavailable), ApprovalControls.tsx (approve only when verification.passed && awaiting_review; posts expected_revision + idempotency key so a double-click publishes once; 409 forces reload + fresh review; reject requires a reason; structured prose edit; approved-PDF export action + queue status), Timeline.tsx (persisted stages only, customer-vs-staff wait, retry on failure). Pages: app/staff/inbox/page.tsx, app/staff/enquiries/[id]/page.tsx.
- Verification: run_checks --prompt 20 -> tests/foundations/test_20.py PASS. apps/web vitest: f18 + f27 + f37 (+f01+f15) = 17 passed. Cross-service feature tests PASS in their suites: gateway test_f03 (demo role switching 404s) -> gateway 28; search test_f32 (net available, negative clamped, unknown warehouse rejected) -> search 80; orchestrator test_f39 (approve-only-verified, double-click once, stale/failed-verification blocked) -> orch 47/1 skip; worker test_f61 (approved-only export, no price/notes) -> worker 22. Python ruff clean; verify_kit PASSED.

Prompts 13–20 complete (this session). Full regression: run_checks --prompt 00..20 all exit 0; --feature F02/F49 exit 0; gateway/search/orchestrator/worker suites + web vitest (17) all green; verify_kit PASSED. The tools/catalog pytest collection error is pre-existing/unrelated (stray tools/catalog/__init__.py) and not exercised by the per-prompt gate.

Completed through 21 (Labelled evaluations):
- tools/evals/run.py + __init__.py: evaluate_case (exact status+compat match; never a model confidence; failures keep actual), run_suite(cases, live=False, *, solve) (injected resolver; deterministic mode imports/calls no OpenAI), dataset_sha256 (pins the fixture), accuracy (excludes unlabelled, reports abstention separately), build_run_receipt (live runs record git SHA + model id), deterministic_solver (seed-42 scenario-keyed resolver; injection text ignored). tests/evals/cases.json: 11 labelled cases covering the four demos + arabic/typo/serial-boundary/ambiguity/multi-item-stock/injection + an unlabelled unreadable case.
- Verification (exit 0): run_checks --prompt 21 -> test_21.py PASS; run_checks --feature F62 -> tests/acceptance/test_f62.py PASS; tests/evals/test_scenarios.py PASS (3) incl. validating the four demo labels against build_scenarios(generate_catalog(42)); ruff clean. Deterministic accuracy 1.0, 3 abstentions + 1 unlabelled reported separately.
- BLOCKED: the live-model evaluation path (needs confirmed OpenAI credit) is separate from the deterministic suite and not run here.

Completed through 22 (Security and failure recovery gate):
- tests/integration/test_security_recovery.py owns assert_disposable_environment(TestConfig) (refuses a production DSN/project ref or non-local/test app_env) and the live security scenario class (foreign sessions, reset races, expired JWT, upload bombs, Redis down, worker crash, stale lease, API timeout, simultaneous approvals) which SKIP without a disposable local Supabase. tests/integration/test_rls.py + test_budget_races.py skip-gated on a disposable DB. tests/e2e/security.spec.ts is a Playwright deliverable (skips without a baseURL). services/gateway/tests/features/test_f04.py (demo isolation) + test_f54.py (JWT malformed/none-alg rejected; DB-sourced roles so forged claims are ignored; assigned-only). apps/web/tests/features/f53.test.tsx (api client maps 503/422/non-JSON to a typed ApiError with request id, no stack leak).
- Verification (exit 0): run_checks --prompt 22 -> test_22.py PASS (disposable guard; require_access foreign/forged/missing -> 404; verify_facts rejects an oversold plan; no secret in the web bundle); gateway suite 36 passed; apps/web vitest 20 passed (adds f53); ruff clean.
- BLOCKED (reported, skipped not faked): all live scenarios needing a disposable local Supabase (auth+storage), Redis and a running app for the Playwright e2e.

Completed through 23 (Observability and credit limits):
- tools/credit_allowance.py: validate_allowance(amount, expires_at, paid_budget) -> CreditAllowance — manually confirmed (never inferred from a key); non-zero paid budget / non-positive amount / expired credit all block. services/gateway/app/metrics.py: get_metrics (staff-only; demos excluded unless include_demo; median review + nearest-rank p95 + summed estimated cost). tools/check_readiness.py: readiness_report (per-subsystem probes; unconfigured/failing = False; lexical vs semantic reported separately).
- Connected through owners (additive, callers preserved): ai/client.py call_structured gains an optional outage-safe tracer that emits a redacted span with request/enquiry ids; ai/budget.py gains reserve_for_request (worst-case atomic reservation; unknown price blocks; uncertain requests retain the reservation); telemetry.py gains LangfuseExporter (lazy import, strict timeout; the Tracer already swallows exporter outages) + build_tracer.
- Packages: langfuse==3.14.5 installed in the dev env and pinned as the partsiq-common optional [trace] extra (lazy-imported; app runs without it). uv.lock re-locked (adds langfuse + opentelemetry deps + protobuf/wrapt/backoff; packaging 26.3->25.0 workspace-wide) — full 00-23 regression + all service suites + verify_kit verified green after the change.
- Verification (exit 0): run_checks --prompt 23 -> test_23.py PASS; --feature F64 + F67 PASS; prompt 01 regression + gateway/search/orchestrator/worker suites green; ruff clean.
- BLOCKED: a live Langfuse sink and the live metrics DB are integration-only; tested with fake exporters/repos.

Completed through 24 (Production containers and Caddy):
- docker-compose.prod.yml: Caddy edge is the ONLY published container (80/443); gateway/search/orchestrator/orchestrator-consumer/worker/sweeper/redis stay on a private bridge network (expose only). App images are immutable (ghcr.io/partsiq/*:${RELEASE_SHA}); caddy/redis pin an @sha256 digest from infra/images.lock.json. One search process; worker (app.dispatcher), sweeper (app.sweeper) and orchestrator-consumer (app.runner) are separate commands over the two app images. read_only rootfs where possible, tmpfs for PDF (/tmp/pdf) and the search cache, json-file logs capped (10m x3), per-service memory/cpu limits. No Kubernetes, no public Redis; all secrets are ${VAR} references.
- Caddyfile: auto-TLS for ${API_DOMAIN}, HSTS/nosniff/DENY headers, reverse_proxy to gateway:8000 with a health probe. services/orchestrator/Dockerfile + services/worker/Dockerfile created; services/gateway + services/search Dockerfiles modified to pin the base by @sha256 digest (lineage preserved). infra/verify_images.py: verify_images(compose) static-rejects mutable tags, missing healthchecks, published internal ports and embedded credentials. infra/images.lock.json records the base digests (to re-verify at deploy).
- Verification (exit 0): run_checks --prompt 24 -> test_24.py PASS (prod compose clean; verifier catches every violation class; all four Dockerfiles digest-pinned; only Caddy publishes 80/443; separate worker/sweeper/consumer commands); ruff clean.
- BLOCKED: building/pushing/running the images needs Docker + a registry; the recorded base digests are placeholders to re-verify against the live registry manifest at deploy (prompt 26/27).

Completed through 25 (CI and controlled deployment):
- .github/workflows/ci.yml: service-isolated Python tests (matrix per suite, APP_ENV=test), frontend lint/tsc/vitest, local-Postgres RLS integration, deterministic evals; least-privilege permissions (contents: read); all actions pinned to recorded commit SHAs. .github/workflows/deploy-backend.yml: workflow_dispatch ONLY (never pull_request), GHCR build/push, a migrate job that runs before the deploy job, deploy gated by the production GitHub environment (manual approval) + the INFRA_READY flag (off until prompt 26), AWS access via OIDC id-token (no static keys). tools/ci_checks.py: check_ci_configuration static-validates SHA pinning, permissions, OIDC/environment gating, migration-before-activation and the no-pull_request rule.
- Verification (exit 0): run_checks --prompt 25 -> test_25.py PASS (committed workflows clean; the checker catches unpinned actions / missing permissions / pull_request deploy / no environment); run_checks --feature F66 -> tests/acceptance/test_f66.py PASS; ruff clean.
- BLOCKED: running CI / building+pushing GHCR images / assuming the AWS OIDC role require GitHub + AWS; the recorded action SHAs must be re-verified against each action's release at setup.

Completed through 26 (AWS free-plan deployment):
- infra/ec2/preflight.py: preflight(account, sizing) -> DeploymentDecision — allows deploy only for a free plan with unexpired credit on an instance whose memory fits the MEASURED peak (BGE-M3 + Chromium) with 20% headroom; free micro is not assumed adequate; ap-south-1 is a proposal the operator verifies. A CLI gate (_main) exits non-zero when blocked. infra/ec2/bootstrap.sh validates the env-file path + refuses a non-0600/0400 secrets file; deploy.sh accepts exactly one hex release SHA (lock + healthcheck + previous-image retention); rollback.sh re-activates the previous immutable SHA and never resets the DB. deploy-backend.yml gains a preflight step before activation (owner wiring; CI config still clean).
- Verification (exit 0): run_checks --prompt 26 -> test_26.py PASS (preflight allow/block cases incl. no-credit/expired/peak>instance/headroom; scripts reject bad SHA / unprotected env file; accept good inputs); prompt 25 + F66 still green; ruff clean.
- BLOCKED: real EC2 provisioning (SSM, encrypted volume, IAM), image pull/activation and SSM access require the AWS account; recorded region/sizing are operator-verified receipts, not provisioned here.

Completed through 27 (Vercel and hosted acceptance):
- tools/hosted_acceptance.py: run_hosted_acceptance(base_url, api_url) -> HostedReceipt — rejects non-HTTPS URLs outside localhost, runs the four demo scenarios (each incl. approval + PDF) via an injected client, and reports exactly which passed/failed; is_available() is the single honest gate (available ONLY when all four pass). With no client wired it refuses rather than fabricate a pass. infra/vercel/README.md: separate preview/prod bindings; only publishable Supabase key + gateway URL are NEXT_PUBLIC; exact-origin CORS (no wildcard); documented free-tier limits (Supabase inactivity pausing, AWS credit expiry, single-host). tests/e2e/hosted.spec.ts: Playwright hosted spec (skips without a baseURL).
- Verification (exit 0): run_checks --prompt 27 -> test_27.py PASS (HTTPS rejection, localhost allowed, no-client refusal, all-pass available, any-failure blocks availability; README public-only + no-wildcard + documented limits); ruff clean.
- BLOCKED: the real hosted run (live Vercel + EC2 + Supabase) and the Playwright hosted spec; deployment is not claimed available until those pass.

=== BUILD COMPLETE (numeric prompts 00-27) ===
Full regression this session: run_checks --prompt 00..27 all exit 0; --feature F02/F49/F62/F64/F66/F67 all exit 0; gateway 36 / search 80 / orchestrator 47(+1 skip) / worker 22; apps/web vitest 20 (6 files); verify_kit PASSED; ruff clean. Every live-infrastructure dependency (Supabase Auth/DB/RLS, Redis, pgvector+BGE-M3/torch, live OpenAI text+vision, Postgres LangGraph checkpointer, Playwright/Chromium, Storage, AWS/EC2/SSM, Vercel, hosted acceptance) remains BLOCKED and is reported as such — never faked. Use `uv sync --all-packages` (a bare `uv sync` prunes member deps).

Remaining (not in the numeric sequence, not requested this session): the F-coverage prompts in prompts/README.md (e.g. F06/F07/F08, F16/F17/F19…, F68/F69 docs) layer additional feature UIs/routes on top of this foundation.

Watch (unchanged): all live infrastructure remains BLOCKED and reported — Supabase Auth/DB/RLS, Redis, pgvector + BGE-M3 (torch not installed), live OpenAI (text + vision), Postgres LangGraph checkpointer, Playwright/Chromium PDF + e2e, Storage. The frontend toolchain (node 25 / pnpm 10.31) is installed and its vitest suite runs; run_checks has no pnpm wiring, so the per-prompt gate is the Python structural test and the vitest suite is run directly (reported, never faked). Use `uv sync --all-packages` (a bare `uv sync` prunes member deps).

Watch: AWS Free Plan eligibility and actual BGE/Chromium sizing; owner-confirmed OpenAI credit; assigned-only permissions; no fake production-readiness claims. Live OpenAI and live-DB behaviour for AI/audit/actor-context remain integration work (tested here only with in-process fakes).

Evidence: docs/SESSION_LOG.md records this session and the coding model. Runtime, Supabase, and hosted acceptance remain implementation work.

=== F-COVERAGE PROMPTS (post 00-27) ===
Executing the remaining F-prompts whose implementation owner is the F-prompt itself (26 total), in prompts/README.md execution order. Gate per feature: owning service's pytest suite (service-located tests), apps/web vitest (UI features), or run_checks --feature (repo-root acceptance tests). File-ownership.json + FLOW.md already pre-register these files/modifiers (kit-authored), so no manifest edits are needed unless a touched file is unregistered. ESLint cannot run in this env (missing @eslint/eslintrc devDep) — vitest is the working web gate.

Completed through F16 (photo quality feedback):
- services/worker/app/features/f16_photo_quality_feedback.py: assess_photo(F16Request)->F16Result — local pre-check BEFORE the paid vision call. Unsupported media type / undecodable bytes / format mismatch / >40 MP bomb -> readable False with a retake code; a decodable, supported image stays readable with advisory guidance codes (low_resolution/too_dark/possible_blur). Blur/dark/low-res never block (advisory). No OCR confidence percentage is produced. dispatcher.photo_quality_gate exposes it through the worker's existing owner (lazy Pillow import).
- apps/web: lib/features/f16_photo_quality_feedback.ts (browser mirror via createImageBitmap+canvas, advisory), components/features/PhotoQualityNotice.tsx (loading/empty/error/success states, maps codes->actionable retake text, submits only typed bytes+media-type). Wired into Chat.tsx (optional pre-upload check) and the landing journey.
- Verification: worker suite 33 passed incl. tests/features/test_f16.py (11 cases); ruff clean; apps/web vitest 20 passed; tsc clean on changed files. Commands: (services/worker) python -m pytest -q; (apps/web) pnpm test.
- BLOCKED: nameplate.py paid-path invocation of the gate (owned by prompt 16, not modified here); live Storage fetch; browser canvas path (real browser only).
- Next: F17 (multi-part enquiries).

Completed through F17 (multi-part enquiries):
- services/orchestrator/app/features/f17_multi_part_enquiries.py: resolve_items(actor, F17Request)->F17Result over an injected ItemPlanningStore. Each item keeps independent quantity/configuration/candidates/selection/status; stock is planned ONCE per selected part and distributed in ordinal order (duplicate parts share one pool -> no double count; later line -> 'unavailable'); unresolved_item_ids returns every non-'ready' item and can_approve_all gates final approval; non-positive quantity -> 422; >20 items -> 400; unauthorized/demo-session-mismatch -> 404; stale expected_revision -> 409.
- routes.py: now a prefix-free parent router mounting the existing /v1/workflow routes (paths unchanged) + a token-guarded /internal router exposing POST /internal/items/resolve (main.py untouched, still includes one router). handlers.unresolved_items(state) shares the single readiness rule.
- apps/web: lib/features/f17_multi_part_enquiries.ts (typed client + canApproveAll) + components/features/ItemList.tsx (per-item status, candidate counts, all-items readiness gate); wired into Chat.tsx + landing journey.
- Verification: orchestrator suite 59 passed + 1 skip incl. tests/features/test_f17.py (12 cases); ruff clean; apps/web vitest 20 passed.
- BLOCKED: live enquiry_items/fulfilment_plans adapter + RLS; the gateway public proxy route; HTTP exercised offline only.
- Next: F19 (enquiry history).

Completed through F19 (enquiry history):
- services/gateway/app/features/f19_enquiry_history.py: list_history(actor, F19Request)->F19Result over an injected HistoryRepository. Owned-only (ownership derived from ActorContext; no owner field on the request to spoof); demo sees only the active generation; keyset pagination on the stable (created_at,id) pair so equal timestamps never duplicate or skip; opaque base64 cursor (invalid -> 422); limit bounded 1..100 (-> 422); over-fetch-by-one yields next_cursor.
- api_v1.py: GET /v1/enquiries wired to the use case. apps/web: lib + HistoryList + app/history/page.tsx (first page on mount, cursor "Load more"); landing nav link to /history.
- Verification: gateway suite 44 passed incl. tests/features/test_f19.py (8 cases: newest-first, foreign-owner-ignored, equal-timestamp no dup/skip across pages, status filter, invalid cursor 422, invalid limit 422, cursor roundtrip, dependency failure); ruff clean; apps/web vitest 20 passed.
- BLOCKED: live enquiries adapter + RLS; DB-level demo-generation filter.
- Next: F55 (saved machines).

Completed through F55 (saved machines):
- services/gateway/app/features/f55_saved_machines.py: save_machine/list_machines/rename_machine/archive_machine over an injected SavedMachineRepository. Idempotent save by request key; duplicate label allowed (UUID identity); owner-scoped so a foreign id is NOT_FOUND; archive is a soft delete (archived_at); saved rows store identifiers only and prefill_from_machine carries no configuration -> re-identify against the current catalogue; blank label/serial or non-positive model -> 422; serial stored verbatim.
- api_v1.py: POST/GET/PATCH(label only)/DELETE /v1/machines. apps/web: lib + SavedMachines component; landing journey mention.
- Verification: gateway suite 56 passed incl. tests/features/test_f55.py (12 cases); ruff clean; apps/web vitest 20 passed.
- BLOCKED: live saved_machines adapter + RLS + idempotency store.
- Next: F56 (repeat enquiry).

Completed through F56 (repeat enquiry):
- services/gateway/app/features/f56_repeat_enquiry.py: repeat_enquiry(actor, F56Request)->F56Result over an injected RepeatRepository. Copies only text/locale/destination/confirmed hints into a new enquiry (fresh id, revision 1); the RepeatSpec has no approval/allocation/draft/signed-URL field so those outcomes are structurally impossible to carry; origin is linked in audit; the full pipeline re-runs; foreign source -> 404; repeated submission deduped by idempotency key.
- api_v1.py: POST /v1/enquiries/{id}/repeat. apps/web: lib + RepeatEnquiry component; landing mention.
- Verification: gateway suite 61 passed incl. tests/features/test_f56.py (5 cases: fresh enquiry + audit + re-run, outcome fields absent from RepeatSpec, ownership 404, dedup, dependency failure); ruff clean; apps/web vitest 20 passed.
- BLOCKED: live enquiries/audit adapter + workflow-start enqueue.
- Next: F59 (catalogue versioning).

Completed through F59 (catalogue versioning):
- tools/catalog/catalog/versioning.py: publish_version(actor, F59Request)->F59Result over an injected PublicationStore + canonical_snapshot (order-independent SHA-256, numeric ids preserved). Optimistic compare-and-set on expected_active_version_id (two publishers cannot leave two active versions -> CONFLICT); catalogue_admin/admin only (else FORBIDDEN); failed publish leaves active unchanged; prior approvals keep their immutable evidence; unknown candidate -> 404.
- worker/app/jobs/catalog_publish.py (re-checks admin from the signed payload, publishes under the store lock, fenced JobResult; store injected, BLOCKED) + dispatcher.register_catalog_publish(); gateway f59_publish_routes.request_publish (validate admin + queue, never inline) + POST /v1/staff/catalogue/publish; catalog `snapshot` CLI subcommand (offline canonical hash); apps/web lib + CatalogueVersions.
- Verification: run_checks --feature F59 -> tests/acceptance/test_f59.py PASS (8 cases: order-independent snapshot, activate, two-publisher CONFLICT leaving one active, failed rollback, immutable prior evidence, idempotent, non-admin 403, unknown 404); worker 33; gateway 61; ruff clean; vitest 20.
- BLOCKED: live catalogue-role publication (advisory lock 710070 + single tx), worker publish execution, gateway->worker enqueue.
- Next: F57 (catalogue browser).

Completed through F57 (catalogue browser):
- services/gateway/app/features/f57_catalogue_browser.py: browse_catalogue(actor, F57Request)->F57Result + part_detail over an injected CatalogueReadStore, ACTIVE published version only. Text/model/category filters, cursor paging on part id; local PartView (supersession/fitment/sources); hostile query is a literal (never SQL); invalid cursor/limit -> 422; no published version -> 404; unknown part -> 404; import-staging rows never surfaced.
- api_v1: GET /v1/catalogue/parts + /v1/catalogue/parts/{part_number}. apps/web: lib + CatalogueBrowser + app/staff/catalogue/page.tsx; landing staff nav link.
- Verification: gateway suite 71 passed incl. tests/features/test_f57.py (10 cases); ruff clean; apps/web vitest 20 passed.
- BLOCKED: live published-version read adapter + search part_detail integration.
- Next: F58 (catalogue imports).

Completed through F58 (catalogue imports):
- services/worker/app/features/f58_catalogue_imports.py: validate_import(actor, F58Request)->F58Result, a DRY RUN over an injected ImportStore. Reads CSV (UTF-8) and XLSX (openpyxl read_only, data_only=False) WITHOUT evaluating formulas (formula cells -> FORMULA_NOT_ALLOWED), rejects macro workbooks (zip vbaProject), enforces 10MiB/50000-row limits, and validates schema/model-references/serial-overlap/supersession-cycles/source-evidence. Never writes published data; catalogue_admin/admin only. dispatcher.register_catalog_import() + validate_import_job lease wrapper.
- NEW PACKAGE: openpyxl==3.1.5 (+ et-xmlfile) — uv pip installed, pinned in worker pyproject, uv.lock additive (23/0). gateway f58_import_routes (create/report/validate, admin-only, queue to worker) + 3 /v1/staff/imports routes. apps/web: lib + ImportWizard + app/staff/imports/page.tsx; landing nav link.
- Verification: worker suite 48 passed incl. tests/features/test_f58.py (15 cases: valid CSV/XLSX, schema, CSV+XLSX formula rejection, unknown model, bad source, serial overlap, supersession cycle, macro rejection, file-too-large, too-many-rows, non-admin 403, missing batch 404, dependency failure); gateway 71; ruff clean; vitest 20.
- BLOCKED: live import_batches store, worker execution, gateway->worker enqueue, real upload path.
- Next: F60 (missing-parts queue).

Completed through F60 (missing-parts queue):
- services/gateway/app/features/f60_missing_parts_queue.py: record_missing (idempotent one row per item, no stock field) + update_missing_part(actor, F60Request)->F60Result over an injected MissingPartsRepository. Valid statuses investigating/resolved/unavailable; resolving requires a staff explanation (-> 422); invalid status -> 422; foreign item -> 404; stale revision -> 409; links back to the enquiry; status updates never create catalogue rows or fabricate stock.
- api_v1: PATCH /v1/staff/missing-parts/{item_id}. apps/web: lib + MissingPartsQueue (Resolve blocked without a note); landing Staff-workspace link.
- Verification: gateway suite 79 passed incl. tests/features/test_f60.py (8 cases: idempotent record no-stock, investigating, resolved-needs-note 422, resolved ok, invalid status 422, foreign 404, stale 409, dependency failure); ruff clean; vitest 20.
- BLOCKED: live missing_parts adapter + RLS + assignment.
- Next: F35 (stock freshness).

Completed through F35 (stock freshness):
- services/search/app/features/f35_stock_freshness.py: check_stock_freshness(actor, F35Request)->F35Result over an injected StockReader + now. Flags any item whose allocation stock_updated_at is in the future, older than max_age_seconds, refreshed since planning, or whose current available can no longer cover the quantity; fresh only when none flagged; max_age<=0 -> 422. search routes.py now a prefix-free parent mounting /v1/search (paths unchanged) + /internal/stock/check. approval.py documents that the locked re-read invokes this gate so stale stock never publishes. apps/web lib + StockFreshness; staff enquiry page is a client island hosting the panel (freshness computed server-side; BLOCKED, panel stays empty rather than fake).
- Verification: search suite 88 passed incl. tests/features/test_f35.py (8 cases: fresh, stale, future, insufficient, refreshed, unknown, max_age 422, dependency failure); orchestrator 59+1skip; ruff clean; vitest 20.
- BLOCKED: live stock reader + orchestrator->search freshness call during approval.
- Next: F29 (evidence page viewer).

Completed through F29 (evidence page viewer):
- services/gateway/app/features/f29_evidence_page_viewer.py: open_evidence(actor, F29Request)->F29Result over an injected EvidenceStore. Assigned reviewer / own demo reviewer only (customer -> 404, reference only); typed evidence_id resolved to doc+page within the revision (unknown/arbitrary -> 404, never a raw Storage key); worker-signed short-lived PDF URL; synthetic=True; stale revision 409; re-call renews an expired link.
- api_v1: POST /v1/staff/evidence/open. apps/web: lib + EvidenceViewer; staff enquiry page (client island) hosts it (signing BLOCKED).
- Verification: gateway suite 87 passed incl. tests/features/test_f29.py (8 cases: assigned open, own-demo open, customer 404, demo-mismatch 404, arbitrary id 404, stale 409, link renewal, dependency failure); ruff clean; vitest 20.
- BLOCKED: worker Storage signer + live access/evidence adapter.
- Next: F31 (candidate comparison, web/vitest).

Completed through F31 (candidate comparison):
- apps/web/lib/features/f31_candidate_comparison.ts: compare_candidates(F31Request)->F31Result — compares 2-3 candidates from the SAME item/revision (foreign candidate or mixed revision throws), building rows for part number / names / evidence / availability with a missing attribute as null. components/features/CandidateComparison.tsx renders the table (null -> "unavailable") and a native keyboard-operable Select button per candidate that submits only the id (no browser-authored facts). Wired into the staff enquiry page island.
- Verification: apps/web vitest 29 passed (7 files, +9 F31 cases: 2/3-way compare, missing attr null, foreign id, stale revision, count bounds, select sends id + keyboard focus, empty/loading). vitest is the gate (no Python owner).
- BLOCKED: live review candidate load + selection POST (page island uses a no-op onAction).
- Next: F38 (correct extracted details, orchestrator).

Completed through F38 (correct extracted details):
- services/orchestrator/app/features/f38_correct_extracted_details.py: correct_extraction(actor, F38Request)->F38Result wraps app.revisions.revise (lock + authorize + stale check + apply) with correction guards: typed ItemCorrection fields only, an empty correction -> 422, a result claiming approved -> 409. ItemCorrection has no status/part/candidate field, so a correction cannot approve or invent facts. handlers.reset_derived_state clears draft/verification/pending and re-enters intake (the recomputation reset). routes.py exposes /internal/enquiries/correct via the internal_router; gateway f38_correction_routes forwards POST /v1/staff/enquiries/{id}/corrections after a review-access check. apps/web: lib + CorrectionEditor; staff enquiry page island.
- Verification: orchestrator 67+1skip incl. tests/features/test_f38.py (8 cases: apply+increment, empty 422, stale 409, foreign 404, approved-result 409, schema cannot invent facts, dependency failure, reset_derived_state); gateway 87; ruff clean; vitest 29.
- BLOCKED: live locked revision transaction + gateway->orchestrator forward.
- Next: F42 (assignments).

Completed through F42 (assignments):
- services/gateway/app/features/f42_assignments.py: assign_enquiry(actor, F42Request)->F42Result over an injected AssignmentRepository. Admin-only (reviewer -> 403); assignee must be an active reviewer (else 422); unassign allowed; stale revision -> 409; idempotent on key; the atomic swap means access changes immediately and a reassignment moves access off the previous reviewer. api_v1 POST /v1/staff/enquiries/{id}/assignment. apps/web lib + AssignmentControl; staff enquiry page island.
- Verification: gateway suite 96 passed incl. tests/features/test_f42.py (9 cases: assign, unassign, non-admin 403, non-reviewer 422, stale 409, idempotent, reassignment moves access, missing 404, dependency failure); ruff clean; vitest 29.
- BLOCKED: live locked assignment transaction + assignment_events + active-reviewer lookup.
- Next: F41 (internal notes).

Completed through F41 (internal notes):
- services/gateway/app/features/f41_internal_notes.py: append_note + list_notes over an injected NotesRepository. Append-only with author+timestamp; assigned-only (else 404); empty or >4000 chars -> 422; idempotent; created_at/id order. Notes never surface to a customer or in the PDF (EnquiryView has no notes field — asserted). api_v1 POST+GET /v1/staff/enquiries/{id}/notes. apps/web lib + InternalNotes (React-escaped); staff enquiry page island.
- Verification: gateway suite 105 passed incl. tests/features/test_f41.py (9 cases: append author/body, empty 422, over-limit 422, unassigned 404, idempotent, customer-view-has-no-notes, dependency failure, list order, list unassigned 404); ruff clean; vitest 29.
- BLOCKED: live append-only notes adapter + idempotency_records.
- Next: F43 (overdue indicators).

Completed through F43 (overdue indicators):
- services/gateway/app/features/f43_overdue_indicators.py: classify_deadline(actor, F43Request)->F43Result over an injected DeadlineStore. due_at = created_at + configurable urgent(4h)/normal(24h) threshold (UTC); overdue only for unresolved states (approved/rejected/failed never overdue); age_seconds clamped >=0; sort_overdue_first helper. api_v1 GET /v1/staff/enquiries/{id}/deadline (server UTC now). apps/web lib + OverdueBadge (labelled a triage aid, not an SLA); staff enquiry page island.
- Verification: gateway suite 115 passed incl. tests/features/test_f43.py (11 cases: normal/urgent windows, approved/rejected never overdue, UTC determinism, age clamp, 404, dependency failure, sort order); ruff clean; vitest 29.
- BLOCKED: live enquiries created_at/urgency/status adapter.
- Next: F44 (conversation summary).

Completed through F44 (conversation summary):
- services/orchestrator/app/features/f44_conversation_summary.py: summarize_enquiry(actor, F44Request)->F44Result via the shared budget-gated call_structured. Staff-only (own-demo/assigned/admin else 404); message text treated as data not instructions (prompt isolation); source_message_ids set in code from the authorized messages (model's ids ignored); revision-bound with an is_stale helper; stale expected revision -> 409; a provider/budget failure raises recoverably and the full conversation stays available. handlers.summary_needs_refresh; routes.py /internal/enquiries/summary; gateway f44_summary_routes + POST /v1/staff/enquiries/{id}/summary (review-access, 202). apps/web lib + ConversationSummary; staff enquiry page island.
- Verification: orchestrator 73+1skip incl. tests/features/test_f44.py (6 cases: code-owned source ids, stale 409, unauthorized 404, budget-failure recoverable, prompt isolation, is_stale/handler helper); gateway 115; ruff clean; vitest 29.
- BLOCKED: live OpenAI summary + conversation store + forward.
- Next: F36 (staff inbox).

Completed through F36 (staff inbox):
- services/gateway/app/features/f36_staff_inbox.py: list_inbox(actor, F36Request)->F36Result over an injected (RLS-backed) InboxRepository. Reviewer sees assigned + own demo; admin sees all; status/priority/overdue/text filters; stable keyset pagination; scoped_total computed in the SAME access scope (never a global count); invalid limit/cursor -> 422. api_v1 GET /v1/staff/enquiries. apps/web lib + InboxFilters; app/staff/inbox/page.tsx rewired to F36. page.tsx already links the staff inbox (staff-nav added earlier) — no further landing change needed.
- Verification: gateway suite 124 passed incl. tests/features/test_f36.py (9 cases: reviewer-assigned-only, admin-all, unassigned hidden, status/overdue/query filters, stable paging + constant scoped_total, limit 422, cursor 422, dependency failure); ruff clean; vitest 29.
- BLOCKED: live scope-aware inbox adapter.
- Next: F07 (Arabic/English interface — web, vitest-gated).

Completed through F07 (Arabic and English interface):
- apps/web: lib/features/f07_arabic_and_english_interface.ts (resolve_locale preference>default-en, derived direction; strict translate throws on a missing key), messages/en.json + ar.json (identical keys), i18n/request.ts (cookie->locale + catalog), LocaleSwitcher (persists the cookie, isolates identifiers with <bdi>, never reloads). layout.tsx now async: reads the `locale` cookie and sets <html lang/dir>.
- Verification: apps/web vitest 34 passed (8 files, +5 F07 cases: default/arabic direction, en/ar key parity, missing-key throw, bdi isolation + dir, unsent draft preserved across a switch).
- BLOCKED: none specific; the server-side cookie read runs only in a real request.
- Next: F08 (light and dark themes).

Completed through F08 (light and dark themes):
- apps/web: lib/features/f08_light_and_dark_themes.ts (resolve_theme saved>system>light; storage-safe read/persist/apply) + ThemeToggle (accessible, client-only init so no hydration mismatch). styles/tokens.css gains dark tokens (:root[data-theme="dark"], AA contrast), a :focus-visible ring and prefers-reduced-motion. layout.tsx injects a pre-hydration no-flash script that sets a React-unmanaged data-theme attribute; page.tsx shows the toggle.
- Verification: apps/web vitest 38 passed (9 files, +4 F08 cases: saved precedence, system fallback, toggle persists + applies, storage-disabled still works).
- BLOCKED: none specific.
- Next: F06 (responsive layouts).

Completed through F06 (responsive layouts):
- apps/web: lib/features/f06_responsive_layouts.ts (get_layout 360->1/768->2/1280->3 columns, compact on mobile, reducedMotion carried) + ResponsiveShell (grid, resize re-measure, controlled override). styles/tokens.css gains html overflow-x:hidden, .pq-scroll-x and .pq-sticky-actions. layout.tsx container width/overflow guard; page.tsx wraps journey+actions in ResponsiveShell.
- Verification: apps/web vitest 44 passed (10 files, +6 F06 cases); f01 still green.
- BLOCKED: none specific (200% zoom / device-width are manual checks).
- Next: F48 (input isolation, orchestrator).

Completed through F48 (input isolation):
- services/orchestrator/app/features/f48_input_isolation.py: validate_tool_call(F48Request)->F48Result — only the read-only allowlist (identify, search_parts) with typed/required/nullable arguments, a 4KB cap, and a step-budget gate; a bool cannot pose as an int; label_tool_result keeps tool results inert data. handlers.guard_tool_call raises VALIDATION_FAILED on a denied call (the specialist dispatch gate); routes.py docstring records the boundary.
- Verification: orchestrator suite 87+1skip incl. tests/features/test_f48.py (14 cases: allow read tool, injected-query-inert, write/role/secret UNKNOWN_TOOL, unknown arg, wrong type, bool-not-int, missing required, non-JSON, non-object, oversized, step-budget, guard raise/pass, labelled result).
- BLOCKED: none specific.
- Next: F63 (metrics dashboard).

Completed through F63 (metrics dashboard):
- services/gateway/app/features/f63_metrics_dashboard.py: metrics_dashboard(actor, F63Request)->F63Result wraps get_metrics (staff-only, demo-excluded by default). Non-admins have the labelled-accuracy evaluation fields withheld (operational counts only); labelled_accuracy returns None on a zero denominator (unavailable, never fabricated). api_v1 GET /v1/staff/analytics. apps/web lib + MetricsDashboard + app/staff/analytics/page.tsx; landing Analytics link.
- Verification: gateway suite 131 passed incl. tests/features/test_f63.py (7 cases: admin eval, reviewer eval withheld, zero-denominator unavailable, demo excluded by default, demo-on-request, non-staff 403, dependency failure); ruff clean; vitest 44.
- BLOCKED: live metrics adapter (ai_usage + decision timestamps + assignment scoping).
- Next: F65 (correction feedback).

Completed through F65 (correction feedback):
- services/gateway/app/features/f65_correction_feedback.py: curate_correction(actor, F65Request)->F65Result + list_corrections over an injected repo. Admin-only; only a REVIEWED correction can become ground truth (unreviewed -> 409); duplicate source or case id -> 409; empty label -> 422; the EvalCaseExport written carries only case_id/approved_expected/source_revision/approved_by — never private_text (structural). api_v1 POST /v1/staff/corrections/{id}/eval-case. apps/web lib + CorrectionFeedback wired into the analytics page.
- Verification: gateway suite 141 passed incl. tests/features/test_f65.py (10 cases: curate, exclude-private-text, non-admin 403, unreviewed 409, dup source 409, dup case 409, empty label 422, missing 404, dependency failure, list before/after); ruff clean; vitest 44.
- BLOCKED: live corrections/eval-case adapter.
- Next: F68 (recruiter documentation — acceptance).

Completed through F68 (recruiter documentation):
- docs/RECRUITER_GUIDE.md: overview, real architecture, quick start, four demo paths, tests, trade-offs, limitations, deterministic-decisions + specialist-tools explanation, and an explicit implementation-status-vs-specification section. README.md links the guide + SESSION_LOG/HANDOVER as measured evidence.
- Verification: run_checks --feature F68 -> tests/acceptance/test_f68.py PASS (6 cases incl. a forbidden-claims scan: no invented accuracy/uptime/clients/production adoption); ruff clean.
- PACKAGE DEVIATION: python-docx==1.2.0 authorized but not installed — no consumer (deliverable is markdown; test validates markdown). Deliberate reduce-scope to avoid an unused dependency + re-lock risk.
- Next: F69 (demo walkthrough).

Completed through F69 (demo walkthrough):
- docs/DEMO_SCRIPT.md (3-min + 8-min scripts across happy path / missing serial / incompatibility / stock split / human review, with caption tracks) + docs/RECORDING_CHECKLIST.md (synthetic-data check, reset, failure handling, verify-every-link; no video claimed until recorded).
- Verification: run_checks --feature F69 -> tests/acceptance/test_f69.py PASS (7 cases incl. forbidden-video-claim scans on both docs); ruff clean.
- BLOCKED: the actual recording (needs the live hosted demo).

=== F-COVERAGE COMPLETE ===
All 26 remaining F-prompts implemented this session (F16,F17,F19,F55,F56,F59,F57,F58,F60,F35,F29,F31,F38,F42,F41,F43,F44,F36,F07,F08,F06,F48,F63,F65,F68,F69), each a separate commit with a pre-fNN tag. The numeric build 00-27 plus all F-coverage prompts are now done. Live infrastructure remains BLOCKED throughout (Supabase/Redis/pgvector+BGE-M3/OpenAI/Chromium/AWS/Vercel/hosted acceptance) and is tested offline with injected fakes, never faked as passing.

## 2026-10-17 — Owner-requested UI revamp (18-ui-revamp)
- State: local UI implementation complete on `prompt/18-ui-revamp`, following the completed build sequence. Supplied PartsIQ reference and Visentix public CSS inspected; Teclusion reference fetch timed out. No hosted Site modified or deployed; existing Next.js/Vercel architecture retained.
- Changes: shared ivory/forest/gold material palette; editorial landing; preserved transparent bilingual logo; CSS-drawn filter illustration; pointer-driven iridescent foil; scroll reveals; linked workspace preview; responsive visible navigation; themed forms/tables/working screens; polished scenario cards and sign-in. Touch/reduced-motion avoids tilt. No dependency, API, schema, catalogue ID or approval changes. Registered previously unlisted UI source ownership with original creation commit provenance.
- Validation: `pnpm --dir apps/web test` → 44 passed in 10 files. `pnpm --dir apps/web exec tsc --noEmit` → exit 0. Initial tsc exposed pre-existing unknown-error access in f53 tests; added explicit ApiError narrowing. `pnpm --dir apps/web build` → exit 0, 16 pages generated; initial sandboxed Turbopack build failed on prohibited local worker-port binding, rerun with escalation succeeded. `git diff --check` → exit 0.
- Browser: `node /tmp/partsiq-ui-qa.cjs` using installed Chromium 1248 and production `next start --hostname 127.0.0.1 --port 3018` → exit 0. Home, demo hub, inbox, architecture, login and mixed-photo walkthrough at 360/768/1440: no horizontal overflow after orbit clipping fix. Pointer transform observed, reduced-motion transform none, dark toggle works, Arabic direction rtl, keyboard Approve publishes the synthetic reply, Reject returns correction without publication, zero page errors. Desktop screenshot visually inspected after scrolling reveals; mobile light/dark inspected. Existing unrelated dev server on 3000 was not stopped; its stale chunks interfered with initial QA, so validation used an isolated production server.
- Limits: Node v25.3.0 is installed here (project pin is 22.22.0); pinned-runtime/hosted acceptance and live backend checks remain external. No claim of complete translated marketing copy: existing locale control and RTL behavior preserved. No public deployment attempted. Rollback tag: `pre-ui-revamp`; revert the implementation commit to roll back this presentation change. Model identifier: not exposed.

Implementation commit: `bc072da` — `feat(web): revamp PartsIQ interface with editorial design and foil parallax`.

## Command workspace update
See docs/reviews/command-workspace.md for new workspace screens, API URL correction, measured checks and unfinished collaboration/RBAC scope. No package pins or migrations changed. Production is not updated by this commit.
