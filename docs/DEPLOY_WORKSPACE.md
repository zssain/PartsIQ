# Releasing the workspace build to the current EC2 host

Current production (verified 2026-10-20): EC2 t3.small `3.111.33.177`, Caddy (auto-HTTPS)
for `partsiq.duckdns.org`, systemd `partsiq` (uvicorn :8000, `~/partsiq`, env
`~/partsiq/.env.runtime`) and `partsiq-web` (Next standalone :3000, `~/partsiq-web`).
`DATA_SOURCE=fixture`, `AI_MODE=fixture`. No database migration is needed for this release: the
runtime keeps state in process memory, and the new SQL migration is for the future Postgres
adapter. Do not apply it to a shared database without a backup.

## 1. Build (on your machine, Node 22.22.0)

```bash
cd apps/web
NEXT_PUBLIC_API_BASE_URL=https://partsiq.duckdns.org \
# optional, only if invited accounts are enabled (public values only):
# NEXT_PUBLIC_SUPABASE_URL=https://<project>.supabase.co NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=<anon key> \
pnpm build
cp -R public .next/standalone/ && mkdir -p .next/standalone/.next && cp -R .next/static .next/standalone/.next/
```

## 2. Upload (keep a rollback copy)

```bash
H=ubuntu@3.111.33.177; K=~/Downloads/partsiq-key.pem
ssh -i $K $H 'rm -rf ~/partsiq.prev && cp -a ~/partsiq ~/partsiq.prev && rm -rf ~/partsiq-web.prev && cp -a ~/partsiq-web ~/partsiq-web.prev'
rsync -az --delete -e "ssh -i $K" apps/api/ $H:~/partsiq/apps/api/ --exclude __pycache__ --exclude .pytest_cache
rsync -az -e "ssh -i $K" libs pyproject.toml uv.lock $H:~/partsiq/
rsync -az -e "ssh -i $K" fixtures/nameplates evals $H:~/partsiq/ --relative   # sample nameplate + labelled set
rsync -az --delete -e "ssh -i $K" apps/web/.next/standalone/ $H:~/partsiq-web/
```

## 3. Environment (append to `~/partsiq/.env.runtime` as needed)

| Variable | Value for the public demo | Notes |
| --- | --- | --- |
| DEMO_ENABLED | true | anonymous sandbox demo |
| COLLABORATION_ENABLED | true | activation flag for agent collaboration |
| FIXTURE_STEP_DELAY_MS | 600 | pacing so visitors can watch and pause |
| DEMO_MAX_WORKSPACES | 400 | memory bound on t3.small |
| SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY | (optional) | enables invited accounts and the users screen; service key stays server-side |
| SUPABASE_JWT_SECRET | (only legacy HS256 projects) | server-side |
| AI_MODE / OPENAI_* / AI_CONFIRMED_ALLOWANCE_USD / AI_ALLOWANCE_EXPIRES_AT | keep fixture | live needs a confirmed allowance and a priced model in `ai/prices.json` |

## 4. Restart and verify

```bash
ssh -i $K $H 'cd ~/partsiq && ~/.local/bin/uv sync --all-packages --frozen && sudo systemctl restart partsiq && sleep 3 && sudo systemctl restart partsiq-web && systemctl is-active partsiq partsiq-web'
curl -s https://partsiq.duckdns.org/health                       # {"status":"ok"}
curl -s https://partsiq.duckdns.org/v1/workspace/status -H "X-Demo-Token: smoke-$(date +%s)" | head -c 300
cd apps/web && E2E_BASE_URL=https://partsiq.duckdns.org node tests/e2e/workspace-app.mjs   # synthetic smoke
```

Confirm the new build is served: `/demo/live` redirects to `/workspace`, and the header
"Workspace" link points to `/workspace`.

## 5. Rollback

```bash
ssh -i $K $H 'rm -rf ~/partsiq && mv ~/partsiq.prev ~/partsiq && rm -rf ~/partsiq-web && mv ~/partsiq-web.prev ~/partsiq-web && sudo systemctl restart partsiq partsiq-web'
```

There is no data migration to undo. A restart clears in-memory demo and account workspaces
(this is a known limitation; see ADR 0002).

## Invited accounts in production

1. In Supabase: Authentication → URL configuration → add `https://partsiq.duckdns.org/login`
   to redirect URLs, and disable public sign-ups.
2. Set SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY on the API, and NEXT_PUBLIC_SUPABASE_URL +
   NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY at web build time. Then rebuild and redeploy.
3. Create the first administrator: invite yourself in the Supabase dashboard, then set
   `app_metadata = {"partsiq_roles": ["admin"]}` on that user (dashboard SQL:
   `update auth.users set raw_app_meta_data = raw_app_meta_data || '{"partsiq_roles":["admin"]}' where email = '<you>';`).
   Invite everyone else from **Users & access**. `tools/provision_accounts.py` refuses
   production by design.
