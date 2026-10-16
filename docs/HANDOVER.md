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

Next: execute prompt 01 (Shared contracts and clients) per prompts/README.md; commit on branch `prompt/01-...`.

Watch: AWS Free Plan eligibility and actual BGE/Chromium sizing; owner-confirmed OpenAI credit; assigned-only permissions; no fake production-readiness claims. uv.lock currently pins the LEGACY common deps (fastapi 0.115.6 etc.); prompt 01 upgrades common to the TECH_SPEC pins (fastapi 0.135.1 …) and re-locks.

Evidence: docs/SESSION_LOG.md records this session and the coding model. Runtime, Supabase, and hosted acceptance remain implementation work.
