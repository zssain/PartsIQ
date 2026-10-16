# Deployment from local build to recruiter demo

## 1. Local development first
Use Python3.12.12,Node22.22.0,uv0.10.9,pnpm10.30.3 and the pinned Supabase CLI. Execute00 through20 before adding features. Start local Supabase with `pnpm exec supabase start`; record its local ports and keys privately. `pnpm exec supabase db reset` is allowed only against the disposable local instance. Start Compose with `docker compose up --build`. Keep gateway bound to127.0.0.1. Run feature checks and the four scenarios without live provider calls using test doubles. Test doubles must never appear as live AI in recruiter UI.

## 2. Supabase dev and prod
Create two free projects if account quota permits. Use different database passwords and restricted service credentials. Apply numbered migrations to dev first,then compare schema receipt. Use migration-only elevated access to initialize checkpointer schema. Configure private buckets and Auth anonymous sign-in; real-customer self-registration remains disabled in the product. Invite staff administratively; seed the first admin using a one-time audited migration/admin command. Never let users choose their staff role.

Set dedicated runtime LOGIN roles with one service-group grant each. Store connection secrets outside git. Use direct/session-compatible connections for checkpoint and transactional operations; do not assume transaction pooling supports every driver/prepared-statement pattern. Verify SSL and bounded pool sizes against actual Supabase connection allowance. Gateway injects app.actor_id only inside a transaction.

Supabase Free may pause after inactivity. Before recruiter outreach,open the project,restore if needed,and run hosted readiness. Do not manufacture traffic merely to claim permanent availability. Free tier is not a backup service-level guarantee: keep reproducible synthetic seed data and a tested export/restore procedure.

## 3. OpenAI free-credit preflight
Keep the owner's OpenAI provider. A valid API key does not expose a guaranteed credit balance. The operator confirms account/project allowance,expiry and model access in the provider console. Prefer a dedicated project/key,disable paid auto-recharge,and ensure unrelated applications cannot consume the same allocation unnoticed.

AI_ENABLED defaults false. Set AI_FREE_CREDIT_USD to an amount no larger than the verified remaining credit after a safety margin,AI_CREDIT_EXPIRES_AT to its actual expiry,and session/day allowances below the total. AI_PAID_BUDGET_USD remains0. The local budget service reserves upper-bound request cost before each attempt. Unknown pricing,expired allowance,provider insufficient_quota or uncertain billing stops new calls. On timeout keep reservation until reconciled; do not retry indefinitely.

The app cannot independently guarantee provider billing status or prevent spending by other keys. No claim of automatically detecting the exact provider balance is permitted. If the account cannot be configured to prevent paid spending,keep live AI disabled; deterministic search/manual entry/review remain available. Do not replace OpenAI or silently switch providers.

Pinned language and vision snapshot: gpt-4.1-mini-2025-04-14. Validate access with a tiny explicitly budgeted probe. Pricing reference checked2026-10-11: input0.40USD/million tokens,output1.60USD/million; cached discounts are not assumed. Image input token accounting must use the documented patch calculation and an upper-bound estimate. No web-search or paid ancillary tools are enabled.

## 4. AWS Free Plan eligibility and sizing
Before provisioning,record account plan,remaining credits,expiry,region and available instance types. New-account Free Plan availability is conditional and time-limited; it is not permanent free EC2. Do not upgrade to a paid account or provision an excluded service automatically. If existing-account eligibility differs,the operator must verify its actual allowance.

Default region proposal is ap-south-1,subject to eligibility. No fixed free instance is claimed adequate. BGE-M3 plus Chromium and all services can exceed micro-instance RAM. Measure search encoder peak memory,PDF peak memory and total idle usage locally. Select an eligible instance with headroom; keep search process count1 and worker concurrency bounded. If no eligible instance can run the measured stack at zero out-of-pocket cost,use local Compose. Do not hide an architectural reduction or claim full semantic functionality on hardware that cannot run it.

Use encrypted disk,SSM administration,no public SSH,security group ingress80/443 only. Avoid NAT Gateway,load balancer or paid domain purchase. A DNS name under an existing domain or a no-cost DNS provider is an operator input. Configure HTTPS and exact CORS origin; raw HTTP public demo is not acceptable. Public IPv4,storage,egress and snapshots can consume credits; include them in the account check.

## 5. Images and secrets
Prompt24 builds images from pinned manifests in spec/images.lock.json and records image digests in release metadata. Build BGE weights into search image using immutable model revision. Store Compose secret environment file root-readable only on the host; never pass secrets as Docker build args. Preserve Caddy data for certificates. Redis is private and recoverable from DB jobs; use bounded persistence/logs. Health probes distinguish lexical readiness from semantic warmup.

## 6. CI and deployment
Prompt25 creates checks and a disabled production deployment workflow. Prompt26 provisions prerequisites and enables it only after successful preflight. GitHub OIDC role trust uses exact repo and production environment subject; only SSM commands to the named instance and image pull permissions are allowed. GHCR images are addressed by digest or immutable release SHA. Production environment approval is the deployment gate,not approval of AI-generated customer recommendations.

Deployment steps: acquire deploy lock;record current release;verify environment and credit expiry;take permitted database backup/export;apply additive migrations using migration identity;start new images;run health/readiness and four synthetic scenarios;switch release marker only when checks pass. On failure,return to previous compatible images and retain diagnostic logs. Never automatically reverse data migrations or delete audit history.

## 7. Vercel
Import the built repository with root directory apps/web. Install using frozen lockfile; build with `pnpm build`. Configure production publishable Supabase values and gateway HTTPS URL. Bind previews to dev project/API or disable backend access until configured. Configure no OpenAI,database or internal-service secrets in NEXT_PUBLIC variables. Confirm anonymous Auth,staff login,CORS,upload,Arabic rendering,approval and PDF on hosted deployment.

Vercel Hobby is used for the personal recruiter portfolio subject to its current terms/limits. A commercial client deployment must reassess plan eligibility rather than inherit an unsupported free-plan promise.

## 8. Readiness before sending recruiters
Restore paused Supabase if needed; verify AWS credits/expiry; confirm AI allowance; run four scenarios; inspect Arabic/mobile screens;verify source/README links;record date and actual latency. Provide a short recorded walkthrough as fallback. Do not present prerecorded results as live model processing.

## 9. Render alternative only
If the owner later selects Render,replace EC2/Caddy deployment instructions with a documented web/background-worker/Redis topology and new cost analysis. Keep Supabase and API contracts. Do not claim Render's free services can host the full persistent worker plus BGE workload without measuring current limits. This alternative is not activated by the kit.

## 10. Sources
https://aws.amazon.com/free/free-tier-faqs/
https://supabase.com/docs/guides/platform/free-project-pausing
https://developers.openai.com/api/docs/models/gpt-4.1-mini
https://help.openai.com/en/articles/8264644-setting-up-and-managing-prepaid-api-billing
https://langfuse.com/pricing
https://vercel.com/docs/plans/hobby
