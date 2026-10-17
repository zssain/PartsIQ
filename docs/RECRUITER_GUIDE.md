# PartsIQ — recruiter guide

A concise, honest walkthrough of what this project is, how it is built, and exactly what is and
is not working. Everything below is a measured fact from this repository or an explicit
configuration note — there are no invented metrics, uptime figures, client relationships or
production-adoption claims.

## Overview

PartsIQ is an AI-assisted spare-parts identification system for equipment distributors. A
customer sends a messy enquiry (English/Arabic/mixed, optionally a nameplate photo). The system
identifies the machine, retrieves only catalogue-compatible parts, plans warehouse fulfilment,
drafts a bilingual reply, and a human reviewer must approve before anything is published. All
data is synthetic.

Core principle: **the LLM reads and writes language; the database and code decide facts.** No
compatibility, quantity, stock or approval decision is ever made by a model.

## Real architecture

Four backend services plus a web app, each with one clear responsibility:

- **gateway** (FastAPI) — the only public surface. Verifies the Supabase bearer token, enforces
  roles and assignment, and calls application use cases. Never runs heavy work inline.
- **search** — preserved legacy domain (machine identification, compatible-set filtering,
  fulfilment planning) plus BGE-M3 semantic retrieval. Read-only specialist tools.
- **orchestrator** — a durable LangGraph workflow: intake → identify → search → choose → plan →
  draft → **deterministic verification** → human review. Pass/fail is decided in code.
- **worker** — asynchronous jobs behind leases (nameplate OCR, approved-PDF export, catalogue
  import/publish) with fencing tokens so a stale revision or old demo generation cannot commit.
- **apps/web** (Next.js 16/React 19) — customer chat + demo, staff review workspace, with
  bilingual (en/ar) UI, light/dark themes and responsive layouts.

### Deterministic decisions and specialist tools

- **Deterministic verification gate** (`services/orchestrator/app/verification.py`): seven named
  pure checks (revision, catalogue version, candidate/configuration membership, source evidence,
  quantity, aggregate allocation). No LLM is ever asked whether verification passed.
- **Read-only specialist tools**: the parts specialist may only call `identify` and
  `search_parts`, with typed, size-bounded arguments inside a 4-call budget (input isolation,
  `features/f48_input_isolation.py`). A prompt-injected instruction cannot call a write tool,
  change roles or reveal secrets; customer/OCR/evidence text is always data, never instructions.
- **Human publication gate**: no recommendation is published without a human approving the
  current revision, bound to the verified fact hash.

## Quick start

```bash
# Python (uv workspace, pinned CPython 3.12.12)
uv sync --all-packages
python tools/run_checks.py --prompt 00        # per-prompt structural gate
python tools/run_checks.py --feature F49       # a mapped acceptance test

# Service test suites (each runs in its own process)
cd services/gateway && python -m pytest -q
cd services/orchestrator && python -m pytest -q
cd services/search && python -m pytest -q
cd services/worker && python -m pytest -q

# Web (Node 22+, pnpm)
cd apps/web && pnpm install && pnpm test
```

## Demo paths

Four synthetic, seed-42 scenarios (`tools/demo`, verified against the catalogue):

1. **Mixed-language photo** — Arabic/English enquiry with a nameplate image → OCR confirmation.
2. **Missing serial** — the system asks a clarifying question rather than guessing.
3. **Incompatible number** — a requested part that is not compatible is refused, with evidence.
4. **Local shortage** — fulfilment is planned across warehouses; a shortfall is shown, not hidden.

Staff then review: match explanations (a match score, never a probability), evidence viewer,
stock-freshness re-check, and an explicit approve/reject with a reason.

## Tests

- Per-prompt structural gate: `tools/run_checks.py --prompt <id>`.
- Deterministic acceptance tests under `tests/acceptance` and per-service `tests/features`.
- The web suite (`pnpm test`, vitest) covers the UI features.
- Exact, current pass counts and the commands actually run are recorded in
  [docs/SESSION_LOG.md](SESSION_LOG.md) and [docs/HANDOVER.md](HANDOVER.md) — those are the
  measured evidence, updated as the build progresses rather than asserted here as a headline.

## Trade-offs

- **Determinism over cleverness**: facts come from the catalogue/DB and code checks, which makes
  the system auditable and safe but means it will abstain or ask rather than guess.
- **Human-in-the-loop**: nothing is published without approval, trading throughput for safety.
- **Synthetic data only**: the whole corpus is fabricated, so the demo is reproducible but is not
  a benchmark against real catalogues.
- **Small, predictable worker**: bounded concurrency keeps the system simple at the cost of raw
  job throughput.

## Limitations

- This is a build on a free-tier footprint. Live infrastructure (Supabase Auth/DB/RLS, Redis,
  pgvector + BGE-M3 weights, live OpenAI text+vision, Playwright/Chromium PDF, AWS/EC2, Vercel,
  the hosted acceptance run) is **specified and wired behind injected ports but BLOCKED** in this
  environment — it is tested offline with fakes, never faked as passing.
- No external messaging, quotation, voice, reservation or order creation.
- The labelled evaluation runs on a small synthetic fixture (`tests/evals`); it is a development
  signal, not a production accuracy, uptime or quality guarantee.

## Implementation status vs specification

- **Implemented and tested here** (deterministic, offline): the verification gate, approval/
  revision transactions, worker leases/sweeper, the specialist tools and input isolation, the
  web customer/staff flows, and the F-coverage features — all exercised by the committed test
  suites recorded in the session log.
- **Specified and wired but BLOCKED** (needs live accounts/credit): every live-infrastructure
  dependency listed under Limitations. These are implementation work, explicitly not claimed as
  available. A written specification is not an implemented feature.
