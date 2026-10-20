# Feature status (2026-10-20, branch `feat/complete-workspace`)

## Capability status (configuration, integration and execution evidence)

"Executed" means run end to end against a real service, not a fake, with the named test or
command. "Dev Supabase" is the owner's project `jihekqczlaokinuylxml` (Tokyo, session pooler)
holding synthetic data only. "Disposable" is a throwaway local Supabase Postgres + GoTrue.

| Feature | Code complete? | Configured? | Executed successfully? | Evidence | Exact remaining blocker |
| --- | --- | --- | --- | --- | --- |
| Invited accounts (Supabase Auth, ES256 JWKS) | Yes | Yes (`.env.prod.local`: URL, publishable key, secret key) | Yes, dev Supabase | sign-in, staff route 403 for a customer, forged token 401; `worker_e2e.py` signs in through GoTrue | Owner: add redirect URLs and disable public signup in the dashboard (see DEPLOY_WORKSPACE.md). Invite the first administrator. |
| Invitation-only access | Yes | Yes | Yes, dev Supabase | `worker_e2e.py`: a valid session for an **uninvited** user gets 403; `test_accounts_auth.py` (forged claims ignored) | None in code. Public signup is still on in the project; the API refuses those accounts anyway. |
| Durable account workspace (PostgreSQL write-through) | Yes | Yes (session pooler, `DATABASE_URL_*`) | Yes: disposable (restart) and dev Supabase (persist + resume) | `restart_recovery.py` 20/20: SIGKILL mid-run → same run resumes, no step twice, approve once, replay `already_applied` | Latency: DB in Tokyo, EC2 in Mumbai. A guided run took 17.2 s from the Mac (≈235 ms RTT per batch). Move the DB to `ap-south-1` or accept it. |
| LangGraph checkpoints in PostgreSQL | Yes | Yes (`DATABASE_URL_WORKFLOW`) | Yes, disposable | `restart_recovery.py` (checkpoints > 0, resumed thread) | None |
| Migrations | Yes (additive; edited/destructive refused) | Yes (`DATABASE_URL_MIGRATION`) | Yes: dev Supabase, CI `supabase/postgres` | `tools/apply_migrations.py` records sha256 per file | None |
| RLS (two-actor isolation, default deny, owner WITH CHECK) | Yes | Yes | Yes, GitHub CI | `tests/integration/test_rls.py` (job `rls-integration`, green) | None |
| Background worker + durable dispatch | Yes (`partsiq/jobs/live.py`) | Local: yes. EC2: **not installed** | Yes, dev Supabase + local Redis | `worker_e2e.py` 24/24: job persisted before any worker exists, SKIP LOCKED claim, fenced finish | Deploy: Redis + `infra/ec2/partsiq-worker.service` on EC2 (needs the owner's go-ahead) |
| Redis queue + recovery | Yes (wake-up only; PostgreSQL is truth) | Local: yes. EC2: no Redis yet | Yes | `worker_e2e.py`: Redis unreachable → job still dispatched from PostgreSQL; worker SIGKILL mid-export → lease expiry → re-dispatch, one export | Same as above |
| Private Storage (nameplates, exports) | Yes (REST, server key) | Yes (4 private buckets exist with MIME/size limits) | Yes, dev Supabase | `worker_e2e.py`: object stored, public URL refused, 60 s signed download | None |
| Nameplate reading with confirmation | Yes | Fixture vision: yes. Live vision: no allowance | Fixture: yes. Live: **no** | `worker_e2e.py`: worker reads the stored photo (CA-110 / 800000), customer confirms, run continues | Live vision needs the confirmed free-credit amount and expiry (see OpenAI row) |
| PDF export of the approved snapshot | Yes (Chromium, network refused, reply escaped) | Local: yes. Image: Chromium shell added. EC2: not installed | Yes, dev Supabase | `worker_e2e.py`: PDF matches recorded sha256; screenshot reviewed (logo, fonts, line breaks) | EC2 deploy (Chromium install). Measured 1.6–2.2 s and ≈440 MB peak RSS per render |
| OpenAI live (intake, reply, specialists, vision) | Yes | Key present; models `gpt-4o-mini` / `gpt-4o`; prices verified (see below); `AI_CONFIRMED_ALLOWANCE_USD=0` | **No** (deliberately) | Settings refuse `AI_MODE=live` without a confirmed, unexpired allowance | **Owner input:** the free/promotional credit amount and its expiry date. A key is not proof of free credit, and no paid fallback exists. |
| Durable AI allowance ledger | Yes (`ai/ledger_pg.py`) | Swapped in automatically in database mode | Yes, CI database | `test_budget_races.py`: 60 concurrent reservations → exactly 33 fit a $1.00 cap; totals survive a new ledger instance | None (activates with live AI) |
| Semantic search (BGE-M3) | Encoder port exists | No: torch / sentence-transformers not installed (B) | No | — | **Host capacity:** BGE-M3 (568 M params) needs about 2.3 GB for fp32 weights alone. The EC2 t3.small has 2 GB shared with the API and web. Not loaded, by rule. Needs a ≥4 GB instance (paid; not provisioned). Lexical + alias search stays. |
| Snowflake + Postgres mirror | Adapter code exists | No: connector not installed (B), credentials absent (D) | No | — | Owner: Snowflake account and key pair plus a confirmed free credit allowance. Not started, to avoid billable compute. |
| GitHub CI | Yes | Yes | Yes, both workflows green on PR #2 | `ci` (legacy + foundations, frontend, rls-integration, evals) and `ci-partsiq` | None |
| Arabic page bodies | See F07 below | — | — | — | — |

**OpenAI Standard tier prices, per 1M tokens** (official pricing page, checked 2026-10-20;
recorded in `apps/api/partsiq/ai/prices.json`):

| Model | Input | Cached input | Output |
| --- | --- | --- | --- |
| gpt-4o-mini | $0.15 | $0.075 | $0.60 |
| gpt-4o | $2.50 | $1.25 | $10.00 |

## Per-feature status

Source inventory: `spec/features.json` (69 features). "Working" means reachable from the
workspace UI, backed by the runtime and covered by a test, in **fixture execution**
(deterministic specialists; real compatibility/fulfilment/verification code; synthetic seed-42
catalogue). The **account workspace is durable in PostgreSQL** when `DATABASE_URL_API` is set.
Demo sandboxes stay in memory by design (anonymous, disposable). "Live" means the OpenAI path,
which is not executed (no confirmed allowance).

Test keys: **R** `apps/api/tests/test_workspace_runtime.py`, **A** `test_accounts_auth.py`,
**W** `apps/web/tests/e2e/workspace-app.mjs` (browser), **U** `apps/web/tests/e2e/accounts.mjs`
(browser, real Supabase Auth), **V** web Vitest, **P** existing per-feature pytest.

| ID | Feature | Screen / route | Endpoint(s) | Access | Test | Status |
| --- | --- | --- | --- | --- | --- | --- |
| F01 | Branded landing | `/` | — | public | V f01 | Working |
| F02 | Demo scenarios and assets | `/demo/scenarios`, sample nameplate | `/v1/demo/scenarios`, `…/attachments/sample` | public / demo | P, W | Working (secondary area) |
| F03 | Demo role switching | Shell "Preview as" | `/v1/me` capabilities | demo (presentational) | V, W | Working |
| F04 | Demo isolation | all | per-session workspace | demo | R, W | Working |
| F05 | Demo reset | Shell "Reset demo" | `/v1/demo/sessions/{id}/reset` | demo | R | Working |
| F06 | Responsive layouts | all workspace screens | — | — | W (mobile) | Working |
| F07 | Arabic and English interface | locale control, RTL | — | — | W (RTL), V f07 | Partial: shell/nav/statuses translated; page body copy English |
| F08 | Light and dark themes | theme control | — | — | V f08, W | Working |
| F09 | Bilingual chat | enquiry detail conversation | `POST /v1/enquiries`, `/messages` | owner | R, W | Working |
| F10 | Structured extraction | enquiry detail items | `/extraction` | owner | R | Working (fixture extractor); live BLOCKED |
| F11 | Clarifying questions | pending panel | run `answer` command | owner | R, W | Working |
| F12 | Conversation memory | revisions carry confirmed inputs | — | owner | R | Working |
| F13 | Private uploads | new enquiry photo | `POST …/attachments` | owner | R (validation), worker_e2e | Working: database mode stores photos in the private `nameplates` bucket; demo keeps bytes in memory |
| F14 | Nameplate OCR | nameplate specialist / intake step | worker `nameplate` job | owner | worker_e2e, W | Working (fixture vision, read by the worker in database mode); live vision needs the allowance |
| F15 | OCR confirmation | pending panel | `confirm_nameplate` command | owner | R | Working |
| F16 | Photo quality feedback | detail "issues" | `/attachments/{id}/quality` | owner | — | Partial (unreadable flag only) |
| F17 | Multi-part enquiries | items list | — | owner | R | Working |
| F18 | Progress timeline | enquiry progress | `/timeline`, `/detail` | owner | P, W | Working |
| F19 | Enquiry history | `/workspace/enquiries` | `/v1/workspace/enquiries` | owner | W | Working |
| F20 | Machine identification | items, evidence | identification service | — | R, P | Working |
| F21 | Machine mismatch detection | clarification "mismatch" | — | — | R | Working |
| F22 | Compatibility gate | evidence region | compatibility search | — | R (rogue proposal) | Working |
| F23 | Aliases and typo matching | — | search | — | eval typo case | Working |
| F24 | Semantic retrieval | — | `/search/capabilities` | — | P | BLOCKED: BGE-M3 exceeds the 2 GB host; lexical + alias search only |
| F25 | Ranked candidates | review candidates table | — | review | W | Working |
| F26 | Ambiguity handling | pending options | `answer` | owner | R, W | Working |
| F27 | Match explanations | review "match basis" | — | review | V f27 | Working |
| F28 | Compatibility references | fitment source lines | — | — | R | Working |
| F29 | Evidence page viewer | — | — | — | — | BLOCKED (private evidence PDFs in Storage) |
| F30 | Old part numbers | catalogue supersession | `/catalogue/parts/{n}/detail` | read | P | Working |
| F31 | Candidate comparison | review candidates table | `/comparison` | review | V f31 | Partial (table; no side-by-side) |
| F32 | Warehouse stock | catalogue/plan | detail | read | P | Working (synthetic stock) |
| F33 | Fulfilment planning | plan lines | — | — | R | Working |
| F34 | Transfer estimates | plan lines (estimate wording) | — | — | R | Working |
| F35 | Stock freshness | approval re-check | approve | review | R (stock change → 409) | Working |
| F36 | Staff inbox | `/workspace/review` | `/v1/workspace/enquiries?scope=review`, `/v1/staff/enquiries` | reviewer (assigned) / admin | U, W | Working |
| F37 | Review workspace | `/workspace/review/{id}` | `/v1/staff/enquiries/{id}[/detail]` | review scope | W, U | Working |
| F38 | Correct extracted details | — | `PATCH /v1/staff/enquiries/{id}/extraction` | review | — | API only (no UI) |
| F39 | Review actions | approve/reject | `/approve`, `/reject` | review.decide | R, U, W | Working |
| F40 | Approval invalidation | revisions / stale banners | `/approval-state` | review | R | Working |
| F41 | Internal notes | review notes | `/notes` | review | — | Working (UI) |
| F42 | Assignments | review assign | `/assignment` | admin | U | Working |
| F43 | Overdue indicators | queue badges, filter | `/deadline` | review | — | Working |
| F44 | Conversation summary | — | `/summary` | review | — | BLOCKED (needs live model) |
| F45 | Reply drafting | draft region (staff edit API) | `PUT …/draft` | review | — | Partial (API; no edit UI) |
| F46 | Verification gate | 7-rule list | `/verification` | review | R, W | Working |
| F47 | Human publication gate | approved reply | `/published-reply` | owner | R, W | Working |
| F48 | Input isolation | instructions as untrusted | controller policy | — | R (policy) | Working |
| F49 | Audit trail | `/workspace/admin/audit` | `/v1/admin/audit` | admin | W, U, rls-integration | Working (append-only in PostgreSQL, enforced by trigger; in memory for demo sandboxes) |
| F50 | Durable workflows | run history | `/workflow`, runs | read | R, restart_recovery | Working: PostgreSQL write-through + LangGraph PostgreSQL checkpoints; restart resumes without repeating steps |
| F51 | Background jobs | `/workspace/admin/jobs` | `/v1/admin/jobs`, `/v1/jobs/{id}` | admin | worker_e2e | Working: PostgreSQL jobs + Redis wake-ups + sweeper (worker not yet installed on EC2) |
| F52 | Retry and dedup | jobs retry, idempotency keys | `/v1/jobs/{id}/retry` | admin | R | Working |
| F53 | Graceful failures | error/empty states | — | — | V f53, W | Working |
| F54 | Access and permissions | nav from `/v1/me` | `/v1/me` | any | V, U | Working |
| F55 | Saved machines | `/workspace/machines` | `/v1/machines`, `/check` | owner | — | Working |
| F56 | Repeat enquiry | detail "Repeat this enquiry" | `/repeat` | owner | — | Working |
| F57 | Catalogue browser | `/workspace/catalogue` | `/v1/catalogue/search`, `/detail` | read | R, W | Working |
| F58 | Catalogue imports | `/workspace/admin/imports` | `/v1/admin/imports…` | catalogue_admin/admin | R, W | Working (CSV; xlsx refused) |
| F59 | Catalogue versioning | versions, compare-and-set publish | `/publish`, `/versions` | catalogue_admin/admin | R | Working |
| F60 | Missing-parts queue | — | `/v1/staff/missing-parts` | review | P | API only |
| F61 | Enquiry PDF | — (API) | `POST /v1/enquiries/{id}/exports`, `GET /v1/exports/{id}/download` | owner / assignee / admin | worker_e2e | Working in database mode (Chromium PDF, private bucket, 60 s signed link); no UI button yet |
| F62 | Labelled evaluations | `/workspace/admin/evaluation` | `/v1/admin/evaluations` | admin | R | Working (real pipeline: 8/10 on `evals/cases.json`) |
| F63 | Metrics dashboard | `/workspace/admin/analytics` | `/v1/admin/analytics` | admin | V, W | Working (measured; nulls when unmeasured) |
| F64 | Latency and AI cost | analytics latency/tokens | `/v1/admin/ai-allowance` | real admin only | R, test_budget_races | Latency working; cost ledger durable (PostgreSQL); live spend not executed |
| F65 | Correction feedback | evaluation corrections | `/v1/admin/corrections` | admin | — | Partial (review flag; curation store not wired) |
| F66 | Tests and CI | — | — | — | CI | Working: `ci` and `ci-partsiq` green; real DB integration job |
| F67 | Traces | run activity | `/traces` | review | — | Working (step trace; no Langfuse) |
| F68 | Recruiter documentation | `docs/RECRUITER_GUIDE.md` | — | — | P f68 | Updated |
| F69 | Demo walkthrough | `docs/DEMO_SCRIPT.md` | — | — | P f69 | Superseded by recruiter walkthrough; no recording claimed |

New in this branch (not in the original 69): agent-collaboration mode, run master controls,
pending delegation consent, invited-account provisioning (`tools/provision_accounts.py`).
