# Feature status (2026-10-20, branch `feat/complete-workspace`)

Source inventory: `spec/features.json` (69 features). "Working" means reachable from the
workspace UI, backed by the runtime and covered by a test, in **fixture execution**
(deterministic specialists; real compatibility/fulfilment/verification code; synthetic seed-42
catalogue). Persistence is **process memory** for every row unless stated otherwise (see ADR
0002). "Live" means the OpenAI path; it is never claimed as verified here.

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
| F13 | Private uploads | new enquiry photo | `POST …/attachments` | owner | R (validation), W (sample) | Working (in-memory bytes; Supabase Storage BLOCKED) |
| F14 | Nameplate OCR | nameplate specialist / intake step | — | owner | W | Fixture: synthetic sample only; live vision BLOCKED |
| F15 | OCR confirmation | pending panel | `confirm_nameplate` command | owner | R | Working |
| F16 | Photo quality feedback | detail "issues" | `/attachments/{id}/quality` | owner | — | Partial (unreadable flag only) |
| F17 | Multi-part enquiries | items list | — | owner | R | Working |
| F18 | Progress timeline | enquiry progress | `/timeline`, `/detail` | owner | P, W | Working |
| F19 | Enquiry history | `/workspace/enquiries` | `/v1/workspace/enquiries` | owner | W | Working |
| F20 | Machine identification | items, evidence | identification service | — | R, P | Working |
| F21 | Machine mismatch detection | clarification "mismatch" | — | — | R | Working |
| F22 | Compatibility gate | evidence region | compatibility search | — | R (rogue proposal) | Working |
| F23 | Aliases and typo matching | — | search | — | eval typo case | Working |
| F24 | Semantic retrieval | — | `/search/capabilities` | — | P | BLOCKED (BGE-M3 not installed); lexical only |
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
| F49 | Audit trail | `/workspace/admin/audit` | `/v1/admin/audit` | admin | W, U | Working (append-only in memory) |
| F50 | Durable workflows | run history | `/workflow`, runs | read | R | Partial: LangGraph checkpoints in memory; schema migration ready, adapter not wired |
| F51 | Background jobs | `/workspace/admin/jobs` | `/v1/admin/jobs`, `/v1/jobs/{id}` | admin | — | Working (runs in-process; no Redis worker) |
| F52 | Retry and dedup | jobs retry, idempotency keys | `/v1/jobs/{id}/retry` | admin | R | Working |
| F53 | Graceful failures | error/empty states | — | — | V f53, W | Working |
| F54 | Access and permissions | nav from `/v1/me` | `/v1/me` | any | V, U | Working |
| F55 | Saved machines | `/workspace/machines` | `/v1/machines`, `/check` | owner | — | Working |
| F56 | Repeat enquiry | detail "Repeat this enquiry" | `/repeat` | owner | — | Working |
| F57 | Catalogue browser | `/workspace/catalogue` | `/v1/catalogue/search`, `/detail` | read | R, W | Working |
| F58 | Catalogue imports | `/workspace/admin/imports` | `/v1/admin/imports…` | catalogue_admin/admin | R, W | Working (CSV; xlsx refused) |
| F59 | Catalogue versioning | versions, compare-and-set publish | `/publish`, `/versions` | catalogue_admin/admin | R | Working |
| F60 | Missing-parts queue | — | `/v1/staff/missing-parts` | review | P | API only |
| F61 | Enquiry PDF | — | `/exports` | owner | — | BLOCKED (Chromium renderer not installed) |
| F62 | Labelled evaluations | `/workspace/admin/evaluation` | `/v1/admin/evaluations` | admin | R | Working (real pipeline: 8/10 on `evals/cases.json`) |
| F63 | Metrics dashboard | `/workspace/admin/analytics` | `/v1/admin/analytics` | admin | V, W | Working (measured; nulls when unmeasured) |
| F64 | Latency and AI cost | analytics latency/tokens | `/v1/admin/ai-allowance` | real admin only | R | Working for latency; cost BLOCKED until live |
| F65 | Correction feedback | evaluation corrections | `/v1/admin/corrections` | admin | — | Partial (review flag; curation store not wired) |
| F66 | Tests and CI | — | — | — | — | Partial: suites pass locally; GitHub workflow setup broken (known) |
| F67 | Traces | run activity | `/traces` | review | — | Working (step trace; no Langfuse) |
| F68 | Recruiter documentation | `docs/RECRUITER_GUIDE.md` | — | — | P f68 | Updated |
| F69 | Demo walkthrough | `docs/DEMO_SCRIPT.md` | — | — | P f69 | Superseded by recruiter walkthrough; no recording claimed |

New in this branch (not in the original 69): agent-collaboration mode, run master controls,
pending delegation consent, invited-account provisioning (`tools/provision_accounts.py`).
