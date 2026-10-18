# Deployment runbook

## Deployment profiles

Local fixture profile is the default and requires no live OpenAI/Snowflake account. It still runs the real application, local Supabase, private storage, workflow, search and approval; AI fixture outputs are visibly labelled. Live development profile uses Supabase dev plus confirmed OpenAI/Snowflake allowance. Hosted profile uses Next.js/Vercel and one AWS EC2 host for Caddy, API, worker and Redis. Supabase production is a separate project. Render is an alternative only if the owner explicitly selects and verifies an appropriate current plan.

## 1 Prepare local tooling

Install the target Python 3.12, Node 22.22.0, pnpm10.30.3, Docker Engine/Compose and the pinned Supabase CLI from infrastructure receipts. Create the repository, copy the kit and execute foundation 00. Preserve the original legacy archive. Copy environment.example to an ignored .env and fill only local Supabase configuration. Run supabase start and inspect the actual local endpoints. Never use a production project URL for local tests.

Run uv venv --python 3.12 and uv pip sync spec/python-requirements.lock after the files exist. Install the frontend from the frozen manifest/lock in foundation 18. Implementation prompts create the following runnable commands; they are not shipped as already completed application code in this kit.

## 2 Initialize local data

Run python tools/apply_postgres.py --environment local after its foundation implementation. It must reject a nonlocal database before applying SQL 001–006. Run python tools/seed_demo.py --source fixture --seed 42. Verify counts, hash, all four scenario expectations, and synthetic evidence assets. Keep real onboarding disabled. Start docker compose -f docker-compose.yml -f infra/compose.fixture.yml up --build and run the feature tests. The API and worker must report fixture provenance; no live model call is made.

## 3 Configure Supabase dev

Create or select the development project within the owner's allowed plan. Apply migrations through the operator credential, then create least-privilege LOGIN roles mapped to API, workflow, worker, search andcatalogue groups. Store their passwords in secrets, not SQL source. Configure auth issuer/audience and JWKS verification; enable anonymous demo signin and invite named staff. Configure redirect URLs for localhost and the intended Vercel development domain. Set private bucket limits/policies from SQL 005. Verify two-user RLS and private downloads before exposing a demo.

## 4 Configure Snowflake dev

Confirm actual trial/account allowance and expiry. If unavailable, continue fixture mode and mark live integration blocked. With an authorized dev account, run the setup tool against PARTSIQ_DEV and the supplied schema/role SQL. Generate/register key-pair service-user credentials locally and store only the public key in Snowflake. Private keys remain secret-mounted files with restrictive permissions. Grant each role only the required database/schema/table and warehouse permissions.

Create one initially suspended X-Small warehouse only after allowance confirmation. Set AUTO_SUSPEND60, AUTO_RESUMEtrue and statement timeout20seconds. Attach a resource monitor based on the confirmed credit budget. Do not select an invented budget value or claim the monitor guarantees zero charges. Avoid Cortex/serverless features. Run python tools/snowflake_preflight.py --environment dev and save sanitized role/version/query receipts. Publish the synthetic source version through the same import/sync flow used by the app and compare the serving hash.

## 5 Enable approved OpenAI usage

Confirm that the owner-provided key has a dedicated free allowance and expiry for the selected text and vision models. Configure the exact accessible model IDs and pricing inputs in the admin allowance record. The key alone is insufficient evidence. Set AI_MODE=live only after preflight succeeds. Test a bounded structured extraction and one synthetic nameplate through the budget wrapper, recording token usage and reservation settlement. Leave fixture mode available as an explicit selection, never an automatic paid fallback.

## 6 Build and deploy backend

Confirm AWS account eligibility, balance, expiry and intended instance/storage/network costs. Benchmark memory before enabling BGE-M3; small free instances may not fit it. Keep semantic capability disabled transparently when capacity is insufficient, while retaining its implementation/tests. Provision only authorized covered resources. Restrict inbound ports toHTTPS/HTTP and owner-controlled SSH access; Redis and API internal ports remain private. Use the owner-controlled domain in Caddy and verifyDNS/HTTPS.

Build the immutable image with the release commit tag. Run docker compose -f docker-compose.yml -f infra/compose.production.yml config to inspect interpolation without printing secret values. Pull/build approved images, run migrations as a one-off operator job, then start API, worker, Redis and Caddy. Check liveness, readiness, durable queue recovery and restricted ports. No LangGraph/search/orchestrator services are deployed. Keep a previous compatible image tag for rollback.

## 7 Deploy frontend

Connect the repository to Vercel with apps/web as the project root. Use the exact build command and packageManager from the manifest. Set NEXT_PUBLIC_API_ORIGIN and matching Supabase public values. Preview environments point todev only; production points toprod only. Private Snowflake/OpenAI/database keys never enter frontend variables. Verify CORS contains the exact deployed origin and no wildcard credential policy. Confirm the owner's current Vercel plan permits the intended demo usage.

## 8 Hosted acceptance

Execute the four demo scenarios inEnglish/Arabic from a clean browser session. Confirm photo extraction, missing serial, incorrect part refusal, warehouse split, review andapprovedPDF. Create a second anonymous visitor and prove it cannot read the first session. Reset a session during a running OCR job and prove the late result cannot reappear. Reassign a real enquiry in dev and prove old reviewer access islost. Compare source/serving version and reporting lag. Record actual timings, not invented targets. Only then mark hosted acceptance passed.

## 9 Operate within allowance

Monitor allowance expiry, worker backlog, failed jobs, stock freshness, active catalogue hash andreporting delay. Stop live scheduled work before confirmed free access expires. AWS and Snowflake free access may be temporary; local fixture mode is the durable demonstration alternative. Back up PostgreSQL andprivate evidence according to the owner-approved retention policy. Do not claim high availability for a single EC2 host. Deployment doesnot change the human approval gate.

## Render alternative

If the owner later chooses Render, run the same API image and an appropriate worker service with privateRedis access and the sameSupabase/Snowflake contracts. Verify current service andworker plan limits before selection. Do not substitute a sleeping web-only process for durable jobs or assume analways-onworker is free. Update ADR002 andrerun hosted acceptance after changing hosting.
